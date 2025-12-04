"""
map_products.py
검색 TOOL + LLM 매핑 Node
"""

import json
import logging
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

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

HIGH_CONF_THRESHOLD = 0.7
LOW_CONF_THRESHOLD = 0.5


class MappingNode:
    """검색 + 매핑 통합 Node."""

    def __init__(
        self,
        llm_client,
        search_tool,
        top_k: int = 5,
        alpha: float = 0.7,
        product_repository: Optional[ProductRepository] = None,
        max_candidates_per_doc: int = 2,
    ):
        self.llm = llm_client
        self.search_tool = search_tool or get_retrieval_tool()
        self.top_k = top_k
        self.alpha = alpha
        self.product_repository = product_repository or ProductRepository()
        self.debug_enabled = settings.MAPPING_DEBUG_ENABLED
        self.max_candidates_per_doc = max_candidates_per_doc

    # ----------------------------------------------------------------------
    # change detection 연계 유틸
    # ----------------------------------------------------------------------
    def _normalize_token(self, value: str) -> str:
        return (
            value.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "_")
        )

    def _extract_change_scope(
        self,
        change_results: List[Dict[str, Any]],
        present_features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        변경 감지 결과에서 검색/매핑에 쓸 힌트를 추출한다.
        """
        if not change_results:
            return {
                "actionable_results": [],
                "pending_results": [],
                "doc_filters": set(),
                "chunk_filters": set(),
                "feature_hints": set(),
                "raw_results": [],
            }

        feature_key_map = {
            self._normalize_token(name): name for name in present_features.keys()
        }
        feature_keys = set(feature_key_map.keys())
        doc_filters: Set[str] = set()
        chunk_filters: Set[str] = set()
        feature_hints: Set[str] = set()
        actionable: List[Dict[str, Any]] = []
        pending: List[Dict[str, Any]] = []

        for result in change_results:
            status = result.get("status")
            change_detected = result.get("change_detected")
            positive_status = (status or "").lower() in (
                "changed",
                "updated",
                "new",
                "modified",
                "added",
            )
            confidence = (
                result.get("confidence_score")
                or result.get("score")
                or result.get("confidence")
                or 0.0
            )

            # 신뢰도/상태에 따른 분류
            is_inconclusive = (status or "").lower() == "inconclusive"
            if change_detected or positive_status:
                if confidence >= HIGH_CONF_THRESHOLD:
                    actionable.append(result)
                elif confidence >= LOW_CONF_THRESHOLD:
                    pending.append(result)
                else:
                    continue
            elif is_inconclusive:
                pending.append(result)
            else:
                # 너무 낮은 신뢰도는 스킵
                continue

            # 문서/청크 식별자 수집 (검색 필터)
            for key in (
                "doc_id",
                "regulation_id",
                "new_regulation_id",
                "legacy_regulation_id",
                "meta_doc_id",
            ):
                val = result.get(key)
                if val:
                    doc_filters.add(str(val))

            meta = result.get("metadata") or {}
            for key in ("doc_id", "meta_doc_id"):
                val = meta.get(key)
                if val:
                    doc_filters.add(str(val))

            for key in (
                "chunk_id",
                "new_chunk_id",
                "legacy_chunk_id",
                "new_ref_id",
                "legacy_ref_id",
            ):
                val = result.get(key)
                if val:
                    chunk_filters.add(str(val))

            # feature 힌트: 명시적 feature 필드 또는 keywords와 이름 매칭
            for key in ("feature", "feature_name", "feature_names"):
                val = result.get(key)
                if isinstance(val, str):
                    normalized = self._normalize_token(val)
                    if normalized in feature_keys:
                        feature_hints.add(feature_key_map[normalized])
                elif isinstance(val, list):
                    for item in val:
                        if not isinstance(item, str):
                            continue
                        normalized = self._normalize_token(item)
                        if normalized in feature_keys:
                            feature_hints.add(feature_key_map[normalized])

            for kw in result.get("keywords", []) or []:
                if not isinstance(kw, str):
                    continue
                normalized_kw = self._normalize_token(kw)
                for norm_name, raw_name in feature_key_map.items():
                    if normalized_kw in norm_name or norm_name in normalized_kw:
                        feature_hints.add(raw_name)

        return {
            "actionable_results": actionable,
            "pending_results": pending,
            "doc_filters": doc_filters,
            "chunk_filters": chunk_filters,
            "feature_hints": feature_hints,
            "raw_results": change_results,
        }

    def _build_change_filters(self, change_scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        doc_filters = change_scope.get("doc_filters") or set()
        chunk_filters = change_scope.get("chunk_filters") or set()
        if doc_filters:
            filters["meta_doc_id"] = list(doc_filters)
        if chunk_filters:
            filters["chunk_id"] = list(chunk_filters)
        return filters or None

    def _select_features_for_mapping(
        self,
        present_features: Dict[str, Any],
        change_scope: Dict[str, Any],
    ) -> List[Tuple[str, Any]]:
        if not present_features:
            return []

        feature_hints: Set[str] = change_scope.get("feature_hints") or set()
        if feature_hints:
            filtered = [
                (name, value)
                for name, value in present_features.items()
                if name in feature_hints
            ]
            if filtered:
                return filtered

        return list(present_features.items())

    def _candidate_matches_change(
        self,
        change_result: Dict[str, Any],
        doc_id: Optional[str],
        chunk_id: Optional[str],
    ) -> bool:
        doc_ids = {
            str(v)
            for v in (
                change_result.get("doc_id"),
                change_result.get("regulation_id"),
                change_result.get("new_regulation_id"),
                change_result.get("legacy_regulation_id"),
                change_result.get("meta_doc_id"),
            )
            if v is not None
        }
        meta = change_result.get("metadata") or {}
        for key in ("doc_id", "meta_doc_id"):
            val = meta.get(key)
            if val:
                doc_ids.add(str(val))

        chunk_ids = {
            str(v)
            for v in (
                change_result.get("chunk_id"),
                change_result.get("new_chunk_id"),
                change_result.get("legacy_chunk_id"),
                change_result.get("new_ref_id"),
                change_result.get("legacy_ref_id"),
            )
            if v is not None
        }

        if chunk_id and chunk_id in chunk_ids:
            return True
        if doc_id and doc_id in doc_ids:
            return True
        return False

    def _match_change_results_to_candidate(
        self,
        change_scope: Dict[str, Any],
        candidate: RetrievedChunk,
    ) -> List[Dict[str, Any]]:
        """검색된 청크와 연관된 변경 감지 결과를 찾아 regulation_meta에 담는다."""
        matches: List[Dict[str, Any]] = []
        meta = candidate.get("metadata") or {}
        doc_id = meta.get("meta_doc_id") or meta.get("doc_id")
        chunk_id = candidate.get("chunk_id")
        for result in (change_scope.get("actionable_results") or []) + (
            change_scope.get("pending_results") or []
        ):
            if self._candidate_matches_change(result, doc_id, chunk_id):
                matches.append(result)
        return matches

    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        product_id = product["product_id"]
        query = self._build_search_query(feature_name, feature_value, feature_unit)
        filters = build_product_filters(product)
        if extra_filters:
            filters.update(extra_filters)

        try:
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
        parts: List[str] = [str(feature_name)]
        if feature_value is not None:
            parts.append(str(feature_value))
        if feature_unit:
            parts.append(feature_unit)

        return " ".join(parts)

    def _prune_candidates(
        self, candidates: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
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

    async def run(self, state: Dict) -> Dict:
        product: Optional[ProductInfo] = state.get("product_info")
        mapping_filters: Dict[str, Any] = state.get("mapping_filters") or {}
        change_results: List[Dict[str, Any]] = (
            state.get("change_detection_results") or []
        )
        if not product:
            product_id = mapping_filters.get("product_id")
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
        present_features = (
            present_state or target_state or product.get("features", {}) or {}
        )
        units = product.get("feature_units", {})

        change_scope = self._extract_change_scope(change_results, present_features)

        mapping_results: List[MappingItem] = []
        mapping_targets: Dict[str, Dict[str, Any]] = {}

        extra_search_filters = {
            key: value
            for key, value in mapping_filters.items()
            if key not in {"product_id"}
        }
        change_search_filters = self._build_change_filters(change_scope)
        merged_search_filters = {}
        for src in (extra_search_filters, change_search_filters):
            if src:
                merged_search_filters.update(src)
        if not merged_search_filters:
            merged_search_filters = None

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

        feature_iterable = self._select_features_for_mapping(
            present_features, change_scope
        )

        # 🔥 feature별로 검색 TOOL → 매핑
        for feature_name, present_value in feature_iterable:
            unit = units.get(feature_name)
            target_value = target_state.get(feature_name)

            # -----------------------------------------
            # a) 검색 TOOL 호출
            # -----------------------------------------
            if self.debug_enabled:
                logger.info(
                    "🔍 Searching feature=%s value=%s unit=%s",
                    feature_name,
                    unit or "-",
                )
            retrieval: RetrievalResult = await self._run_search(
                product, feature_name, present_value, unit, merged_search_filters
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

                regulation_meta = dict(cand.get("metadata") or {})
                change_matches = self._match_change_results_to_candidate(
                    change_scope, cand
                )
                if change_matches:
                    regulation_meta["change_detection_matches"] = change_matches

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
                    regulation_meta=regulation_meta,
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
        state["mapping_actionable_changes"] = change_scope.get("actionable_results", [])
        state["mapping_pending_changes"] = change_scope.get("pending_results", [])
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
