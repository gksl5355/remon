"""LangGraph node: map_products."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Dict, List, Protocol, Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai_pipeline.state import AppState
from app.config.settings import settings
from app.core.database import AsyncSessionLocal
from app.vectorstore.vector_client import VectorClient, VectorMatch
from app.vectorstore.vector_schema import MappingResult, ProductSnapshot
from db.models import MappingResult as MappingResultORM
from db.models import Product as ProductORM


# -----------------------------------------------------------------------------
# Config & Port definitions
# -----------------------------------------------------------------------------


@dataclass
class MappingConfig:
    top_k: int
    threshold: float
    alpha: float
    semantic_weight: float
    numeric_weight: float
    condition_weight: float

    @classmethod
    def from_settings(cls) -> "MappingConfig":
        return cls(
            top_k=settings.MAPPING_TOP_K,
            threshold=settings.MAPPING_THRESHOLD,
            alpha=settings.MAPPING_ALPHA,
            semantic_weight=settings.MAPPING_SEMANTIC_WEIGHT,
            numeric_weight=settings.MAPPING_NUMERIC_WEIGHT,
            condition_weight=settings.MAPPING_CONDITION_WEIGHT,
        )

    def normalize(self) -> "MappingConfig":
        total = self.semantic_weight + self.numeric_weight + self.condition_weight
        if not total:
            return self
        return MappingConfig(
            top_k=self.top_k,
            threshold=self.threshold,
            alpha=self.alpha,
            semantic_weight=self.semantic_weight / total,
            numeric_weight=self.numeric_weight / total,
            condition_weight=self.condition_weight / total,
        )


class ProductRepository(Protocol):
    async def fetch_for_mapping(
        self, *, country: str | None, category: str | None
    ) -> Sequence[ProductSnapshot]: ...


class MappingSink(Protocol):
    async def save(self, results: Sequence[MappingResult]) -> None: ...


# -----------------------------------------------------------------------------
# Repository & Sink implementations (RDB 기본값)
# -----------------------------------------------------------------------------


class RDBProductRepository(ProductRepository):
    """제품 RDB 조회 기본 구현."""

    # TODO(remon-ai): @bofoto 만약 조회 관련해서 분리해서 가져갈 준비되면 이 구현을 어댑터 처럼 구현하여 가져가주세요

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self._session_maker = session_maker

    async def fetch_for_mapping(
        self, *, country: str | None, category: str | None
    ) -> Sequence[ProductSnapshot]:
        stmt = select(ProductORM)
        if country:
            stmt = stmt.where(ProductORM.export_country == country)
        if category:
            stmt = stmt.where(ProductORM.category == category)

        async with self._session_maker() as session:
            rows = await session.execute(stmt)
            products = rows.scalars().all()

        return [ProductSnapshot.model_validate(p) for p in products]


class RDBMappingSink(MappingSink):
    """매핑 결과를 RDB `mapping_result` 테이블에 저장."""

    # TODO(remon-ai): @bofoto 만약 조회 관련해서 분리해서 가져갈 준비되면 이 구현을 어댑터 처럼 구현하여 가져가주세요

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self._session_maker = session_maker

    async def save(self, results: Sequence[MappingResult]) -> None:
        if not results:
            return

        async with self._session_maker() as session:
            orm_rows = []
            for result in results:
                product_id = _to_int_or_none(result.product_id)
                regulation_id = _to_int_or_none(result.regulation_id)
                if product_id is None or regulation_id is None:
                    logger.warning(
                        "MappingSink skip persist: invalid ids product={} regulation={}",
                        result.product_id,
                        result.regulation_id,
                    )
                    continue

                orm_rows.append(
                    MappingResultORM(
                        product_id=product_id,
                        regulation_id=regulation_id,
                        hybrid_score=result.final_score,
                        matched_fields=result.matched_fields,
                        impact_level=result.impact_level,
                    )
                )

            if not orm_rows:
                return
            session.add_all(orm_rows)
            await session.commit()


class NoOpMappingSink(MappingSink):
    async def save(
        self, results: Sequence[MappingResult]
    ) -> None:  # pragma: no cover - noop
        return


# -----------------------------------------------------------------------------
# Core mapping logic
# -----------------------------------------------------------------------------


@dataclass
class MapProductsDependencies:
    vector_client: VectorClient
    product_repository: ProductRepository
    mapping_sink: MappingSink
    config: MappingConfig

    @classmethod
    def default(cls) -> "MapProductsDependencies":
        vector_client = VectorClient.from_settings()
        session_maker = AsyncSessionLocal
        product_repo = RDBProductRepository(session_maker)
        sink: MappingSink
        if settings.MAPPING_SINK_TYPE.lower() == "rdb":
            sink = RDBMappingSink(session_maker)
        else:
            sink = NoOpMappingSink()

        return cls(
            vector_client=vector_client,
            product_repository=product_repo,
            mapping_sink=sink,
            config=MappingConfig.from_settings().normalize(),
        )


class MapProductsNode:
    """제품 ↔ 규제 매핑 노드 구현."""

    def __init__(self, deps: MapProductsDependencies):
        self.deps = deps

    async def __call__(self, state: AppState) -> Dict[str, Any]:
        return await self.run(state)

    async def run(self, state: AppState) -> Dict[str, Any]:
        metadata = state.metadata or {}
        country = metadata.get("country")
        category = metadata.get("category")

        self._log_config_snapshot(state.run_id)

        products = await self.deps.product_repository.fetch_for_mapping(
            country=country, category=category
        )
        if not products:
            logger.warning("map_products: no products fetched for filters {}", metadata)
            return {"mapped_products": []}

        where_filters = _build_regulation_where(metadata)
        mapped: List[MappingResult] = []
        query_tasks = []

        start_ts = perf_counter()
        for product in products:
            query_text = _build_product_query_text(product)
            query_tasks.append(
                asyncio.create_task(
                    self._query_and_score_product(
                        product=product,
                        query_text=query_text,
                        where_filters=where_filters,
                    )
                )
            )

        results_per_product = await asyncio.gather(*query_tasks)
        for product_results in results_per_product:
            mapped.extend(product_results)

        elapsed_ms = (perf_counter() - start_ts) * 1000
        await self.deps.mapping_sink.save(mapped)

        logger.info(
            "map_products: mapped {} pairs ({:.2f} ms)",
            len(mapped),
            elapsed_ms,
        )

        if state.error_log is None:
            state.error_log = []
        state.error_log.append(
            f"map_products: mapped={len(mapped)} elapsed_ms={elapsed_ms:.1f}"
        )

        return {"mapped_products": [result.model_dump() for result in mapped]}

    def _log_config_snapshot(self, run_id: str | None) -> None:
        cfg_dict = asdict(self.deps.config)
        logger.info(
            "map_products config snapshot run_id=%s cfg=%s sink=%s",
            run_id,
            cfg_dict,
            settings.MAPPING_SINK_TYPE,
        )

    async def _query_and_score_product(
        self,
        *,
        product: ProductSnapshot,
        query_text: str,
        where_filters: Dict[str, Any] | None,
    ) -> List[MappingResult]:
        query_response = await self.deps.vector_client.query(
            query_text=query_text,
            alpha=self.deps.config.alpha,
            n_results=self.deps.config.top_k,
            where=where_filters,
        )

        return self._score_product(product, query_response)

    def _score_product(
        self, product: ProductSnapshot, matches: Sequence[VectorMatch]
    ) -> List[MappingResult]:
        if not matches:
            return []

        scored_results: List[MappingResult] = []
        product_dict = product.as_dict()

        for match in matches:
            candidate_metadata = match.payload or {}
            numeric_ratio, numeric_fields = _compute_numeric_ratio(
                product_dict, candidate_metadata
            )
            condition_ratio, condition_fields = _compute_condition_ratio(
                product_dict, candidate_metadata
            )
            semantic_score = match.score

            final_score = (
                self.deps.config.semantic_weight * semantic_score
                + self.deps.config.numeric_weight * numeric_ratio
                + self.deps.config.condition_weight * condition_ratio
            )

            if final_score < self.deps.config.threshold:
                continue

            matched_fields = numeric_fields + condition_fields
            reason = (
                f"{product.name or product.id} ↔ {match.id} "
                f"semantic={semantic_score:.2f} numeric={numeric_ratio:.2f} "
                f"condition={condition_ratio:.2f}"
            )

            scored_results.append(
                MappingResult(
                    product_id=str(product.id),
                    regulation_id=str(match.id),
                    final_score=final_score,
                    hybrid_score=semantic_score,
                    dense_score=match.dense_score,
                    sparse_score=match.sparse_score,
                    numeric_ratio=numeric_ratio,
                    condition_ratio=condition_ratio,
                    matched_fields=matched_fields,
                    reason=reason,
                    metadata={
                        "product": product_dict,
                        "regulation": candidate_metadata,
                    },
                )
            )

        scored_results.sort(key=lambda r: r.final_score, reverse=True)
        return scored_results


# -----------------------------------------------------------------------------
# Helper data functions
# -----------------------------------------------------------------------------


def _compute_numeric_ratio(
    product: Dict[str, Any], regulation_meta: Dict[str, Any]
) -> tuple[float, List[str]]:
    matches = 0
    total = 0
    matched_fields: List[str] = []

    # TODO(remon-ai): 전처리 스키마 확정 후 `_limit/_direction` 가정 검증/보완.
    for key, limit in regulation_meta.items():
        if not key.endswith("_limit"):
            continue
        if not isinstance(limit, (int, float)):
            continue

        field = key[: -len("_limit")]
        product_value = product.get(field)
        if product_value is None:
            continue

        direction = regulation_meta.get(f"{field}_direction", "<=")
        total += 1
        if _compare_numeric(product_value, limit, direction):
            matches += 1
            matched_fields.append(field)

    ratio = matches / total if total else 1.0
    return ratio, matched_fields


def _compare_numeric(value: float, limit: float, direction: str) -> bool:
    if direction == ">=":
        return value >= limit
    return value <= limit


def _compute_condition_ratio(
    product: Dict[str, Any], regulation_meta: Dict[str, Any]
) -> tuple[float, List[str]]:
    evaluations = 0
    matches = 0
    matched_fields: List[str] = []

    for key, expected in regulation_meta.items():
        field, comparator = _parse_condition_field(key)
        if not field:
            continue

        product_value = product.get(field)
        if product_value is None:
            continue

        evaluations += 1
        if _evaluate_condition(product_value, expected, comparator):
            matches += 1
            matched_fields.append(field)

    ratio = matches / evaluations if evaluations else 1.0
    return ratio, matched_fields


def _parse_condition_field(key: str) -> tuple[str | None, str | None]:
    # TODO(remon-ai): 전처리에서 제공하는 최종 접미사 규칙에 맞춰 suffix 리스트 보완.
    for suffix in ("_required", "_allowed", "_prohibited"):
        if key.endswith(suffix):
            return key[: -len(suffix)], suffix
    if key.endswith("_position_required"):
        return key.replace("_position_required", "_position"), "_required"
    if key.endswith("_visibility_required"):
        return key.replace("_visibility_required", "_visibility"), "_required"
    return None, None


def _evaluate_condition(value: Any, expected: Any, comparator: str | None) -> bool:
    if comparator == "_prohibited":
        return value != expected
    if comparator == "_allowed":
        if isinstance(expected, list):
            return value in expected
        return value == expected
    # `_required` 기본
    return value == expected


def _build_regulation_where(metadata: Dict[str, Any]) -> Dict[str, Any] | None:
    filters = {}
    if metadata.get("country"):
        filters["country"] = metadata["country"]
    if metadata.get("category"):
        filters["category"] = metadata["category"]
    return filters or None


def _build_product_query_text(product: ProductSnapshot) -> str:
    attrs = product.as_dict()
    tokens: List[str] = []
    for key in ("name", "category", "export_country"):
        value = attrs.get(key)
        if value:
            # TODO(remon-ai): 기술용어사전 적용해서 이름/카테고리 등을 정규화한 토큰으로 확장.
            tokens.append(str(value))

    detail_tokens = [f"{k}:{v}" for k, v in attrs.items() if k not in ("id", "name")]
    tokens.extend(detail_tokens)
    return " ".join(tokens)


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# entry point
# -----------------------------------------------------------------------------


_default_node = MapProductsNode(MapProductsDependencies.default())


async def map_products_node(state: AppState) -> Dict[str, Any]:
    """LangGraph entry point."""

    return await _default_node(state)
