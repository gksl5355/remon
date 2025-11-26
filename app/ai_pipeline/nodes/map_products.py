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
    ):
        self.llm = llm_client
        self.search_tool = search_tool or get_retrieval_tool()
        self.top_k = top_k
        self.alpha = alpha  # 🔥 dynamic hybrid weight
    
    # 수정: Repository 생성 (클래스만 변경)
        self.product_repository = product_repository or ProductRepository()
        self.debug_enabled = settings.MAPPING_DEBUG_ENABLED

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
    def _build_prompt(self, feature_name, feature_value, feature_unit, chunk_text):
        feature = {
            "name": feature_name,
            "value": feature_value,
            "unit": feature_unit,
        }
        feature_json = json.dumps(feature, ensure_ascii=False)
        return (
            MAPPING_PROMPT.replace("{feature}", feature_json).replace("{chunk}", chunk_text)
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

    # ----------------------------------------------------------------------
    # 3) LLM 매핑 호출
    # ----------------------------------------------------------------------
    async def _call_llm(self, prompt: str) -> Dict:
        try:
            res = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
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
        features = product["features"]
        units = product.get("feature_units", {})

        mapping_results: List[MappingItem] = []

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
                product.get("name", "unknown"),
                len(features),
                self.top_k,
                self.alpha,
            )

        # 🔥 feature별로 검색 TOOL → 매핑
        for feature_name, value in features.items():
            unit = units.get(feature_name)

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
            if self.debug_enabled:
                logger.info(
                    "   ↳ candidates=%d",
                    len(retrieval["candidates"]),
                )

            # -----------------------------------------
            # b) LLM 매핑 수행
            # -----------------------------------------
            for cand in retrieval["candidates"]:
                prompt = self._build_prompt(
                    feature_name, value, unit, cand["chunk_text"]
                )
                llm_out = await self._call_llm(prompt)

                parsed: MappingParsed = llm_out.get("parsed", {})

                item = MappingItem(
                    product_id=product_id,
                    feature_name=feature_name,
                    applies=llm_out["applies"],
                    required_value=llm_out["required_value"],
                    current_value=llm_out["current_value"],
                    gap=llm_out["gap"],
                    regulation_chunk_id=cand["chunk_id"],
                    regulation_summary=cand["chunk_text"][:120],
                    regulation_meta=cand["metadata"],
                    parsed=parsed,
                )
                mapping_results.append(item)

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
        )
        state["mapping"] = mapping_payload
        state["mapping_results"] = mapping_payload
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
        key in context for key in ("llm_client", "search_tool", "top_k", "alpha")
    )
    if has_override:
        node = _build_mapping_node(
            llm_client=context.get("llm_client"),
            search_tool=context.get("search_tool"),
            top_k=context.get("top_k"),
            alpha=context.get("alpha"),
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

    logger.info(
        "📒 Mapping preview (showing %d/%d items):", len(preview), len(items)
    )
    for idx, item in enumerate(preview, 1):
        logger.info(
            "  %d) feature=%s applies=%s required=%s current=%s chunk=%s",
            idx,
            item["feature_name"],
            item["applies"],
            item["required_value"],
            item["current_value"],
            item["regulation_chunk_id"],
        )


def _persist_mapping_snapshot(
    product: ProductInfo,
    items: List[MappingItem],
    state: AppState,
    top_k: int,
    alpha: float,
) -> Optional[str]:
    if not settings.MAPPING_DEBUG_DIR:
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
