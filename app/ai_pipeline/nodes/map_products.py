"""
map_products.py
검색 TOOL + LLM 매핑 Node
"""

import json
import logging
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING
from collections import defaultdict
# Protocol, TYPE_CHECKING 추가

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

try:  # pragma: no cover - import guard
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment]

from app.ai_pipeline.state import (
    ProductInfo,
    RetrievedChunk,
    RetrievalResult,
    MappingItem,
    MappingParsed,
    MappingResults,
    AppState,
    MappingContext,
)

from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT
from app.ai_pipeline.tools.retrieval_utils import build_product_filters
from app.ai_pipeline.tools.retrieval_tool import (
    RetrievalOutput,
    get_retrieval_tool,
)
from app.config.settings import settings
from app.core.database import AsyncSessionLocal

# 추가: Repository import
from app.core.repositories.product_repository import ProductRepository


if TYPE_CHECKING:
    from app.ai_pipeline.tools.retrieval_tool import RetrievalOutput
else:
    class RetrievalOutput(Protocol):
        results: List[Dict[str, Any]]
        metadata: Dict[str, Any]


logger = logging.getLogger(__name__)


# repositories/product_repository.py로 이동

# FEATURE_UNIT_MAP: Dict[str, str] = {
#     "nicotin": "mg",
#     "tarr": "mg",
#     "battery": "mAh",
#     "label_size": "mm^2",
# }
# BOOLEAN_FEATURES = {"menthol", "incense", "security_auth"}
# DEFAULT_EXPORT_COUNTRY = "US"
# PRODUCT_SELECT_BASE = """
# SELECT
#     p.product_id,
#     p.product_name,
#     p.product_category,
#     p.nicotin,
#     p.tarr,
#     p.menthol,
#     p.incense,
#     p.battery,
#     p.label_size,
#     p.security_auth,
#     COALESCE(pec.country_code, :default_country) AS export_country
# FROM products p
# LEFT JOIN product_export_countries pec
#     ON pec.product_id = p.product_id
# """


# class ProductRepository:
#     """RDB에서 제품 정보를 읽어 MappingNode가 소비하는 형태로 직렬화한다."""

#     def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
#         self._session_factory = session_factory

#     async def fetch_product(self, product_id: Optional[int]) -> ProductInfo:
#         params = {"default_country": DEFAULT_EXPORT_COUNTRY}
#         if product_id is not None:
#             query = text(
#                 PRODUCT_SELECT_BASE
#                 + " WHERE p.product_id = :pid ORDER BY p.product_id LIMIT 1"
#             )
#             params["pid"] = product_id
#         else:
#             query = text(PRODUCT_SELECT_BASE + " ORDER BY p.product_id LIMIT 1")

#         async with self._session_factory() as session:
#             result = await session.execute(query, params)
#             row = result.mappings().first()

#         if not row:
#             raise ValueError("제품 정보를 찾을 수 없습니다.")

#         return self._serialize_product(dict(row))

#     def _serialize_product(self, row: Dict[str, Any]) -> ProductInfo:
#         features: Dict[str, Any] = {}
#         feature_units: Dict[str, str] = {}

#         for field, unit in FEATURE_UNIT_MAP.items():
#             value = row.get(field)
#             if value in (None, ""):
#                 continue
#             features[field] = value
#             feature_units[field] = unit

#         for field in BOOLEAN_FEATURES:
#             value = row.get(field)
#             if value is None:
#                 continue
#             features[field] = bool(value)
#             feature_units[field] = "boolean"

#         product: ProductInfo = {
#             "product_id": str(row["product_id"]),
#             "name": row.get("product_name"),
#             "export_country": row.get("export_country") or DEFAULT_EXPORT_COUNTRY,
#             "category": row.get("product_category"),
#             "features": features,
#             "feature_units": feature_units,
#         }
#         return product


class MappingNode:
    """
    검색 + 매핑 통합 Node
    - 검색은 외부 search_tool(TOOL CALL)로 처리
    - search_tool 시그니처는 아직 미정이므로 wrapper 내부 TODO 처리
    """

    def __init__(
        self,
        llm_client,
        search_tool,  # 🔥 LangGraph TOOL 자체
        top_k: int = 5,
        alpha: float = 0.7,  # 🔥 hybrid dense/sparse 비율
        product_repository: Optional[ProductRepository] = None,
        max_candidates_per_doc: int = 2,
    ):
        self.llm = llm_client
        self.search_tool = search_tool or get_retrieval_tool()
        self.top_k = top_k
        self.alpha = alpha  # 🔥 dynamic hybrid weight
    
    # 수정: Repository 생성 (클래스만 변경)
        self.product_repository = product_repository or ProductRepository()
        self.debug_enabled = settings.MAPPING_DEBUG_ENABLED
        self.max_candidates_per_doc = max_candidates_per_doc

    # ----------------------------------------------------------------------
    # 1) 검색 TOOL 호출 wrapper (search_tool 인터페이스 확정되면 이 부분만 수정)
    # ----------------------------------------------------------------------
    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        검색 TOOL을 호출하는 wrapper.
        Hybrid 검색 Tool을 호출하고 state 스키마에 맞춰 변환한다.
        """

        product_id = product["product_id"]
        query = self._build_search_query(feature_name, feature_value, feature_unit)
        filters = build_product_filters(product)
        if extra_filters:
            filters.update(extra_filters)

        try:
            # TODO(remon-tuning): once live RetrievalTool is connected, benchmark per-feature
            # top_k/alpha/filter settings instead of relying on demo defaults.
            tool_result: RetrievalOutput = await self.search_tool.search(
                query=query,
                strategy="hybrid",
                top_k=self.top_k,
                alpha=self.alpha,
                filters=filters or None,
            )
        except Exception as exc:
            logger.warning("retrieval tool 호출 실패: %s", exc)
            return RetrievalResult(
                product_id=product_id,
                feature_name=feature_name,
                feature_value=feature_value,
                feature_unit=feature_unit,
                candidates=[],
            )

        candidates: List[RetrievedChunk] = []
        for item in tool_result["results"]:
            candidates.append(
                RetrievedChunk(
                    chunk_id=item.get("id", ""),
                    chunk_text=item.get("text", ""),
                    semantic_score=item.get("scores", {}).get("final_score", 0.0),
                    metadata=item.get("metadata", {}),
                )
            )

        return RetrievalResult(
            product_id=product_id,
            feature_name=feature_name,
            feature_value=feature_value,
            feature_unit=feature_unit,
            candidates=candidates,
        )

    # ----------------------------------------------------------------------
    # 2) 매핑 프롬프트 생성 (local 처리)
    # ----------------------------------------------------------------------
    def _build_prompt(
        self,
        feature_name,
        present_value,
        target_value,
        feature_unit,
        chunk_text,
    ):
        feature = {
            "name": feature_name,
            "present_value": present_value,
            "target_value": target_value,
            "unit": feature_unit,
        }
        feature_json = json.dumps(feature, ensure_ascii=False)
        return MAPPING_PROMPT.replace("{feature}", feature_json).replace(
            "{chunk}", chunk_text
        )

    def _build_search_query(self, feature_name, feature_value, feature_unit):
        """
        검색 Tool에 전달할 기본 쿼리 문자열 생성.
        """
        parts: List[str] = [str(feature_name)]
        if feature_value is not None:
            parts.append(str(feature_value))
        if feature_unit:
            parts.append(feature_unit)

        return " ".join(parts)

    def _prune_candidates(
        self, candidates: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        중복 chunk와 동일 문서 과잉 후보를 제거한다.
        - 동일 chunk_id 중복 제거
        - 같은 문서(meta_doc_id 기준)에서는 상위 N개까지만 유지
        """
        seen_chunks = set()
        doc_counts = defaultdict(int)
        pruned: List[RetrievedChunk] = []

        for cand in candidates:
            chunk_id = cand.get("chunk_id")
            if chunk_id in seen_chunks:
                continue
            meta = cand.get("metadata", {}) or {}
            doc_id = meta.get("meta_doc_id") or meta.get("doc_id")
            if doc_id:
                if doc_counts[doc_id] >= self.max_candidates_per_doc:
                    continue
                doc_counts[doc_id] += 1

            seen_chunks.add(chunk_id)
            pruned.append(cand)

        return pruned

    # ----------------------------------------------------------------------
    # 3) LLM 매핑 호출
    # ----------------------------------------------------------------------
    async def _call_llm(self, prompt: str) -> Dict:
        try:
            res = await self.llm.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(res.choices[0].message.content)

        except Exception:
            return {
                "applies": False,
                "required_value": None,
                "current_value": None,
                "gap": None,
                "parsed": {
                    "category": None,
                    "requirement_type": "other",
                    "condition": None,
                },
            }

    # ----------------------------------------------------------------------
    # 4) LangGraph Node entrypoint
    # ----------------------------------------------------------------------
    async def run(self, state: Dict) -> Dict:
        product: Optional[ProductInfo] = state.get("product_info")
        mapping_filters: Dict[str, Any] = state.get("mapping_filters") or {}
        if not product:
            filters = state.get("mapping_filters") or {}
            product_id = filters.get("product_id")
           
    # 기존 호출 방식    
            # product = await self.product_repository.fetch_product(
            #     int(product_id) if product_id is not None else None
            # )
            # state["product_info"] = product
    # 수정: Repository 호출 방식 변경 (session 전달)
            async with AsyncSessionLocal() as session:
                product = await self.product_repository.fetch_product_for_mapping(
                    session,
                    int(product_id) if product_id is not None else None
                )
            state["product_info"] = product


        product_id = product["product_id"]
        product_name = product.get("product_name", product.get("name", "unknown"))
        mapping_spec = product.get("mapping") or {}
        target_state = mapping_spec.get("target") or {}
        present_state = mapping_spec.get("present_state") or {}
        # present_state가 비어있으면 target 혹은 구 버전 features를 활용해 최소한의 매핑을 진행한다.
        features = present_state or target_state or product.get("features", {}) or {}
        units = product.get("feature_units", {})

        mapping_results: List[MappingItem] = []
        mapping_targets: Dict[str, Dict[str, Any]] = {}

        extra_search_filters = {
            key: value
            for key, value in mapping_filters.items()
            if key not in {"product_id"}
        }
        if not extra_search_filters:
            extra_search_filters = None

        if self.debug_enabled:
            logger.info(
                "🧭 Mapping start: product=%s name=%s features=%d top_k=%d alpha=%.2f",
                product_id,
                product_name,
                len(features),
                self.top_k,
                self.alpha,
            )
            if not features:
                logger.info("💤 매핑 대상 특성이 없습니다. mapping.present_state나 target을 확인하세요.")

        # 🔥 feature별로 검색 TOOL → 매핑
        for feature_name, value in features.items():
            unit = units.get(feature_name)
            target_value = target_state.get(feature_name)

            # -----------------------------------------
            # a) 검색 TOOL 호출
            # -----------------------------------------
            if self.debug_enabled:
                logger.info(
                    "🔍 Searching feature=%s value=%s unit=%s",
                    feature_name,
                    value,
                    unit or "-",
                )
            retrieval: RetrievalResult = await self._run_search(
                product, feature_name, value, unit, extra_search_filters
            )
            original_count = len(retrieval["candidates"])
            retrieval["candidates"] = self._prune_candidates(retrieval["candidates"])
            pruned_count = len(retrieval["candidates"])
            if self.debug_enabled:
                logger.info(
                    "   ↳ candidates=%d (pruned to %d)",
                    original_count,
                    pruned_count,
                )

            # -----------------------------------------
            # b) LLM 매핑 수행
            # -----------------------------------------
            for cand in retrieval["candidates"]:
                prompt = self._build_prompt(
                    feature_name,
                    value,
                    target_value,
                    unit,
                    cand["chunk_text"],
                )
                llm_out = await self._call_llm(prompt)

                parsed: MappingParsed = llm_out.get("parsed", {})
                required_value = llm_out.get("required_value")
                current_value = llm_out.get("current_value")
                if (
                    llm_out.get("applies")
                    and required_value is None
                    and target_value is not None
                ):
                    required_value = target_value
                if current_value is None and value is not None:
                    current_value = value

                item = MappingItem(
                    product_id=product_id,
                    feature_name=feature_name,
                    applies=llm_out["applies"],
                    required_value=required_value,
                    current_value=current_value,
                    gap=llm_out["gap"],
                    regulation_chunk_id=cand["chunk_id"],
                    regulation_summary=cand["chunk_text"][:120],
                    regulation_meta=cand["metadata"],
                    parsed=parsed,
                )
                mapping_results.append(item)
                # feature별 대표 target 요약: required_value가 있는 applies 항목을 우선 저장
                if item["applies"]:
                    existing = mapping_targets.get(feature_name)
                    has_req = item.get("required_value") is not None
                    replace = False
                    if existing is None:
                        replace = True
                    elif existing.get("required_value") is None and has_req:
                        replace = True
                    if replace:
                        mapping_targets[feature_name] = {
                            "required_value": item.get("required_value"),
                            "chunk_id": item.get("regulation_chunk_id"),
                            "doc_id": item.get("regulation_meta", {}).get("meta_doc_id"),
                        }

                if self.debug_enabled:
                    logger.info(
                        "🧩 applies=%s required=%s current=%s chunk=%s (%s)",
                        item["applies"],
                        item["required_value"],
                        item["current_value"],
                        item["regulation_chunk_id"],
                        item["feature_name"],
                    )

        # -----------------------------------------
        # c) 전역 State 업데이트
        # -----------------------------------------
        mapping_payload = MappingResults(
            product_id=product_id,
            items=mapping_results,
            targets=mapping_targets,
        )
        state["mapping"] = mapping_payload
        state["mapping_results"] = mapping_payload
        state["mapping_targets"] = mapping_targets
        if self.debug_enabled:
            _log_mapping_preview(product_id, mapping_results)
            snapshot_path = _persist_mapping_snapshot(
                product,
                mapping_results,
                state,
                self.top_k,
                self.alpha,
            )
            if snapshot_path:
                state["mapping_debug"] = {
                    "snapshot_path": snapshot_path,
                    "total_items": len(mapping_results),
                }

        return state


_DEFAULT_LLM_CLIENT = None
_DEFAULT_PRODUCT_REPOSITORY: Optional[ProductRepository] = None
_DEFAULT_MAPPING_NODE: Optional[MappingNode] = None


def _get_default_llm_client():
    """AsyncOpenAI 싱글톤을 구성한다."""
    global _DEFAULT_LLM_CLIENT
    if _DEFAULT_LLM_CLIENT is not None:
        return _DEFAULT_LLM_CLIENT

    if AsyncOpenAI is None:
        raise RuntimeError(
            "openai 패키지를 찾을 수 없습니다. `pip install openai` 후 다시 시도하세요."
        )

    _DEFAULT_LLM_CLIENT = AsyncOpenAI()
    return _DEFAULT_LLM_CLIENT


def _get_default_product_repository() -> ProductRepository:
    # global _DEFAULT_PRODUCT_REPOSITORY
    # if _DEFAULT_PRODUCT_REPOSITORY is None:
    #     _DEFAULT_PRODUCT_REPOSITORY = ProductRepository(AsyncSessionLocal)
    # return _DEFAULT_PRODUCT_REPOSITORY
    """ 수정: Repository 생성 방식 간소화"""
    global _DEFAULT_PRODUCT_REPOSITORY
    if _DEFAULT_PRODUCT_REPOSITORY is None:
        _DEFAULT_PRODUCT_REPOSITORY = ProductRepository()
    return _DEFAULT_PRODUCT_REPOSITORY


def _build_mapping_node(
    *,
    llm_client=None,
    search_tool=None,
    top_k: Optional[int] = None,
    alpha: Optional[float] = None,
    product_repository: Optional[ProductRepository] = None,
    max_candidates_per_doc: int = 2,
) -> MappingNode:
    """MappingNode 인스턴스를 생성한다."""
    resolved_llm = llm_client or _get_default_llm_client()
    resolved_top_k = top_k if top_k is not None else settings.MAPPING_TOP_K
    resolved_alpha = alpha if alpha is not None else settings.MAPPING_ALPHA
    resolved_repo = product_repository or _get_default_product_repository()
    return MappingNode(
        llm_client=resolved_llm,
        search_tool=search_tool,
        top_k=resolved_top_k,
        alpha=resolved_alpha,
        product_repository=resolved_repo,
        max_candidates_per_doc=max_candidates_per_doc,
    )


def _get_default_mapping_node() -> MappingNode:
    """파이프라인 전용 기본 MappingNode."""
    global _DEFAULT_MAPPING_NODE
    if _DEFAULT_MAPPING_NODE is None:
        _DEFAULT_MAPPING_NODE = _build_mapping_node()
    return _DEFAULT_MAPPING_NODE


async def map_products_node(state: AppState) -> AppState:
    """
    LangGraph entrypoint wrapping MappingNode.

    state["mapping_context"]를 통해 테스트/특수 실행 시 LLM 또는 Tool을 주입할 수 있다.
    """

    context: MappingContext = state.get("mapping_context", {}) or {}
    has_override = any(
        key in context
        for key in ("llm_client", "search_tool", "top_k", "alpha", "max_candidates_per_doc")
    )
    if has_override:
        node = _build_mapping_node(
            llm_client=context.get("llm_client"),
            search_tool=context.get("search_tool"),
            top_k=context.get("top_k"),
            alpha=context.get("alpha"),
            max_candidates_per_doc=context.get("max_candidates_per_doc", 2),
        )
    else:
        node = _get_default_mapping_node()

    return await node.run(state)


__all__ = ["MappingNode", "map_products_node"]


def _log_mapping_preview(product_id: str, items: List[MappingItem]) -> None:
    max_items = max(1, settings.MAPPING_DEBUG_MAX_ITEMS)
    preview = items[:max_items]
    if not preview:
        logger.info("📭 Mapping produced no items for product=%s", product_id)
        return

<<<<<<< HEAD

# -----------------------------------------------------------------------------
# Core mapping logic
# -----------------------------------------------------------------------------


@dataclass
class MapProductsDependencies:
    vector_client: VectorClient
    product_repository: ProductRepository
    mapping_sink: MappingSink
    config: MappingConfig
    # 🆕 Tools 추가
    retrieval_tool: RetrievalTool
    filter_builder: FilterBuilder

    @classmethod
    def default(cls) -> "MapProductsDependencies":
        vector_client = VectorClient.from_settings()
        session_maker = AsyncSessionLocal
        product_repo = RDBProductRepository(session_maker)
        
        # 🆕 Tools 초기화
        retrieval_tool = RetrievalTool(vector_client=vector_client)
        filter_builder = FilterBuilder()
        
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
            retrieval_tool=retrieval_tool,
            filter_builder=filter_builder,
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

        # 🆕 FilterBuilder 사용
        where_filters = self.deps.filter_builder.build_filters(
            country=country,
            category=category,
            metadata=metadata
        )
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

=======
    logger.info(
        "📒 Mapping preview (showing %d/%d items):", len(preview), len(items)
    )
    for idx, item in enumerate(preview, 1):
>>>>>>> 9c8d2e5de60743a693e60af5e8d67ba0c3fc7bc2
        logger.info(
            "  %d) feature=%s applies=%s required=%s current=%s chunk=%s",
            idx,
            item["feature_name"],
            item["applies"],
            item["required_value"],
            item["current_value"],
            item["regulation_chunk_id"],
        )


<<<<<<< HEAD
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
        # 🆕 RetrievalTool 사용 (고급 검색)
        query_response = await self.deps.retrieval_tool.search(
            query=query_text,
            strategy="hybrid",  # 하이브리드 검색 전략
            top_k=self.deps.config.top_k,
            filters=where_filters,
            alpha=self.deps.config.alpha,
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
    """레거시 필터 빌더 (FilterBuilder로 대체됨)."""
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
=======
def _persist_mapping_snapshot(
    product: ProductInfo,
    items: List[MappingItem],
    state: AppState,
    top_k: int,
    alpha: float,
) -> Optional[str]:
    if not settings.MAPPING_DEBUG_DIR:
>>>>>>> 9c8d2e5de60743a693e60af5e8d67ba0c3fc7bc2
        return None

    target_dir = Path(settings.MAPPING_DEBUG_DIR)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - disk trouble
        logger.warning("Failed to create mapping debug dir: %s", exc)
        return None

    product_id = product["product_id"]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    doc_id = None
    preprocess_results = state.get("preprocess_results") or []
    if preprocess_results:
        doc_id = preprocess_results[0].get("doc_id")
    doc_suffix = doc_id or "unknown-doc"
    filename = f"{timestamp}_{product_id}_{doc_suffix}.json"
    snapshot_path = target_dir / filename

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "product": product,
        "preprocess_summary": state.get("preprocess_summary"),
        "mapping_config": {
            "top_k": top_k,
            "alpha": alpha,
        },
        "total_items": len(items),
        "items": items,
    }

    snapshot_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=_json_safe_encoder,
        ),
        encoding="utf-8",
    )
    logger.info("📝 Mapping snapshot saved: %s", snapshot_path)
    return str(snapshot_path)


def _json_safe_encoder(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
