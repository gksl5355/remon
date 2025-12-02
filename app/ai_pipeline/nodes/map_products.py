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


logger = logging.getLogger(__name__)


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
            product_id = mapping_filters.get("product_id")

            # 기존 호출 방식
            # product = await self.product_repository.fetch_product(
            #     int(product_id) if product_id is not None else None
            # )
            # state["product_info"] = product
            # 수정: Repository 호출 방식 변경 (session 전달)
            async with AsyncSessionLocal() as session:
                product = await self.product_repository.fetch_product_for_mapping(
                    session, int(product_id) if product_id is not None else None
                )
            state["product_info"] = product

        product_id = product["product_id"]
        product_name = product.get("product_name", product.get("name", "unknown"))
        mapping_spec = product.get("mapping") or {}
        target_state = mapping_spec.get("target") or {}
        present_state = mapping_spec.get("present_state") or {}
        # present_state가 비어있으면 target 혹은 구 버전 features를 활용해 최소한의 매핑을 진행한다.
        present_features = (
            present_state or target_state or product.get("features", {}) or {}
        )
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
                len(present_features),
                self.top_k,
                self.alpha,
            )
            if not present_features:
                logger.info(
                    "💤 매핑 대상 특성이 없습니다. mapping.present_state나 target을 확인하세요."
                )

        # 🔥 feature별로 검색 TOOL → 매핑
        for feature_name, present_value in present_features.items():
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
                product, feature_name, present_value, unit, extra_search_filters
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
                    present_value,
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
                if current_value is None and present_value is not None:
                    current_value = present_value

                item = MappingItem(
                    product_id=product_id,
                    product_name=product_name,
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
                            "doc_id": item.get("regulation_meta", {}).get(
                                "meta_doc_id"
                            ),
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
        # 매핑 결과(required_value)를 product_info.mapping.target에 반영해 이후 노드가 바로 비교할 수 있게 한다.
        product_mapping = product.get("mapping") or {}
        updated_target = dict(product_mapping.get("target") or {})
        for fname, target_info in mapping_targets.items():
            required_value = target_info.get("required_value")
            if required_value is not None:
                updated_target[fname] = required_value
        product_mapping["target"] = updated_target
        product["mapping"] = product_mapping
        state["product_info"] = product

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
    """수정: Repository 생성 방식 간소화"""
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
        for key in (
            "llm_client",
            "search_tool",
            "top_k",
            "alpha",
            "max_candidates_per_doc",
        )
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

    logger.info("📒 Mapping preview (showing %d/%d items):", len(preview), len(items))
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
