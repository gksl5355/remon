"""
module: map_products.py
description: 검색 TOOL + LLM 매핑 Node
author: AI Agent
created: 2025-01-18
updated: 2025-12-09
dependencies:
    - openai
    - app.ai_pipeline.tools.retrieval_tool
    - app.core.repositories.product_repository
"""

import asyncio
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
        top_k: int = 10,
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
        self._llm_semaphore = None

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
                    # 완전 일치 우선, 부분 일치는 보조
                    if normalized_kw == norm_name:
                        feature_hints.add(raw_name)
                    elif normalized_kw in norm_name or norm_name in normalized_kw:
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
        recovered_hints: Optional[Set[str]] = None,
    ) -> Tuple[List[Tuple[str, Any]], List[str]]:
        """
        변경 힌트/복구 힌트가 있으면 해당 feature만 선택.
        힌트가 없으면 전체 feature 매핑 (Legacy 있지만 변경 없는 경우 대응).
        """
        unknown: List[str] = []
        if not present_features:
            return [], unknown

        hints: Set[str] = set(change_scope.get("feature_hints") or set())
        if recovered_hints:
            hints |= recovered_hints

        if hints:
            # 힌트가 있으면 해당 feature만 선택
            filtered = [
                (name, value)
                for name, value in present_features.items()
                if name in hints
            ]
            unknown = [hint for hint in hints if hint not in present_features]
            logger.info(f"🎯 힌트 기반 매핑: {len(filtered)}개 feature 선택")
            return filtered, unknown

        # 힌트가 없으면 전체 feature 매핑 (Legacy 있지만 변경 없는 경우)
        all_features = [
            (name, value)
            for name, value in present_features.items()
            if name != "feature_units"  # feature_units는 제외
        ]
        logger.info(f"🔍 전체 feature 매핑: {len(all_features)}개 feature")
        return all_features, unknown

    async def _classify_change_requirement(
        self,
        change_hint: Dict[str, Any],
        present_features: Dict[str, Any],
        sem,
    ) -> Dict[str, Any]:
        """
        change_detection 결과를 기반으로
        - existing_feature: 우리 스펙에 있음 → matched_feature 반환
        - new_requirement: 신규 요구 → 알림용 기록
        - ambiguous: 불확실 → 알림용 기록
        """
        features_list = [
            {"name": name, "unit": present_features.get("feature_units", {}).get(name), "value": val}
            for name, val in present_features.items()
            if name != "feature_units"
        ]
        prompt = {
            "task": "classify_change_requirement",
            "change_hint": {
                "change_type": change_hint.get("change_type"),
                "keywords": change_hint.get("keywords", []),
                "numerical_changes": change_hint.get("numerical_changes", []),
                "new_snippet": change_hint.get("new_snippet") or change_hint.get("new_text"),
                "legacy_snippet": change_hint.get("legacy_snippet") or change_hint.get("legacy_text"),
                "section_ref": change_hint.get("section_ref"),
            },
            "product_features": features_list,
            "instructions": (
                "Given the change hint and product feature list, decide whether it matches an existing feature."
                " If not, mark as new_requirement. If unsure, mark ambiguous.\n"
                "Output JSON only: "
                "{\"match_status\": \"existing_feature\"|\"new_requirement\"|\"ambiguous\", "
                "\"matched_feature\": \"name or null\", "
                "\"reason\": \"string\", "
                "\"suggested_hint\": \"string or null\"}"
            ),
        }
        async with sem:
            try:
                res = await self.llm.chat.completions.create(
                    model="gpt-5-nano",
                    messages=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                )
                return json.loads(res.choices[0].message.content)
            except Exception:
                return {
                    "match_status": "ambiguous",
                    "matched_feature": None,
                    "reason": "llm_error",
                    "suggested_hint": None,
                }

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

    def _build_regulation_filters(self, regulation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """state.regulation 메타데이터 기반 검색 필터."""
        if not regulation:
            return {}
        filters: Dict[str, Any] = {}
        for key in ("country", "citation_code", "effective_date", "title", "regulation_id"):
            val = regulation.get(key)
            if val:
                filters[key] = val
        return filters

    def _merge_filters(self, *filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        merged: Dict[str, Any] = {}
        for src in filters:
            if src:
                merged.update(src)
        return merged or None

    def _build_change_query(self, change_hint: Optional[Dict[str, Any]]) -> Optional[str]:
        """변경 감지 힌트에서 핵심 키워드만 추출 (간결한 쿼리)."""
        if not change_hint:
            return None
        parts: List[str] = []
        # 키워드 우선 (가장 핵심적)
        for kw in change_hint.get("keywords", []) or []:
            if isinstance(kw, str) and kw.strip():
                parts.append(kw.strip())
        # 수치 변경 정보 추가
        for num_change in change_hint.get("numerical_changes", []) or []:
            for key in ("new_value", "field"):
                val = num_change.get(key)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())
        # 최대 5개 토큰으로 제한 (과도한 쿼리 방지)
        return " ".join(parts[:5]) if parts else None

    def _merge_candidate_lists(
        self,
        base: List[RetrievedChunk],
        extra: List[RetrievedChunk],
    ) -> List[RetrievedChunk]:
        """
        chunk_id 기준으로 병합하며 더 높은 semantic_score를 유지한다.
        """
        merged: Dict[str, RetrievedChunk] = {}
        for cand in base + extra:
            cid = cand.get("chunk_id")
            if cid in merged:
                if (cand.get("semantic_score") or 0) > (
                    merged[cid].get("semantic_score") or 0
                ):
                    merged[cid] = cand
            else:
                merged[cid] = cand
        return list(merged.values())

    def _choose_change_hint(self, change_scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        actionable = change_scope.get("actionable_results") or []
        pending = change_scope.get("pending_results") or []
        if actionable:
            return actionable[0]
        if pending:
            return pending[0]
        return None

    def _build_trace_entries(
        self,
        mapping_results: List[MappingItem],
        regulation_meta: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        now_ts = datetime.utcnow().isoformat() + "Z"
        entries: List[Dict[str, Any]] = []
        for item in mapping_results:
            if not item.get("applies"):
                continue
            rerank_meta = item.get("regulation_meta", {}).get("rerank", {}) or {}
            change_status = (
                "pending" if rerank_meta.get("pending") else "applied"
            )
            entries.append(
                {
                    "feature": item.get("feature_name"),
                    "applied_value": item.get("required_value"),
                    "regulation_record_id": item.get("regulation_chunk_id"),
                    "mapping_score": rerank_meta.get("final_confidence")
                    or item.get("regulation_meta", {}).get("semantic_score"),
                    "change_status": change_status,
                    "evidence": {
                        "legacy_snippet": None,
                        "new_snippet": item.get("regulation_summary"),
                    },
                    "regulation_info": {
                        "country": regulation_meta.get("country"),
                        "citation_code": regulation_meta.get("citation_code"),
                        "title": regulation_meta.get("title"),
                        "effective_date": regulation_meta.get("effective_date"),
                        "regulation_id": regulation_meta.get("regulation_id"),
                    },
                    "updated_at": now_ts,
                }
            )
        return entries

    def _rule_rank_candidates(
        self,
        candidates: List[RetrievedChunk],
        change_hint: Optional[Dict[str, Any]],
        top_n: int = 3,
    ) -> List[RetrievedChunk]:
        """
        규칙 기반 스코어로 상위 후보 추림.
        - semantic_score 우선
        - change keywords, numerical_change 텍스트 매칭에 가점
        """
        if not candidates:
            return []

        keywords = set()
        numbers = set()
        if change_hint:
            for kw in change_hint.get("keywords", []) or []:
                if isinstance(kw, str):
                    keywords.add(self._normalize_token(kw))
            for num_entry in change_hint.get("numerical_changes", []) or []:
                for key in ("legacy_value", "new_value"):
                    val = num_entry.get(key)
                    if isinstance(val, str):
                        numbers.add(val.lower())

        def score(cand: RetrievedChunk) -> float:
            base = cand.get("semantic_score") or 0.0
            text = (cand.get("chunk_text") or "").lower()
            bonus = 0.0
            for kw in keywords:
                if kw in text:
                    bonus += 0.05
            for num in numbers:
                if num and num in text:
                    bonus += 0.05
            return base + bonus

        ranked = sorted(candidates, key=score, reverse=True)
        return ranked[:top_n]

    def _build_rerank_prompt(
        self,
        change_hint: Dict[str, Any],
        candidates: List[RetrievedChunk],
    ) -> str:
        """
        rerank + 변경 요약 + 요구사항 추출을 한 번에 수행하도록 LLM 프롬프트 구성.
        """
        evidence = {
            "change_type": change_hint.get("change_type"),
            "confidence_score": change_hint.get("confidence_score"),
            "new_snippet": change_hint.get("new_snippet")
            or change_hint.get("new_text")
            or change_hint.get("new_ref_text"),
            "legacy_snippet": change_hint.get("legacy_snippet")
            or change_hint.get("legacy_text")
            or change_hint.get("legacy_ref_text"),
            "keywords": change_hint.get("keywords", []),
            "numerical_changes": change_hint.get("numerical_changes", []),
        }
        cand_payload = []
        for idx, cand in enumerate(candidates):
            cand_payload.append(
                {
                    "id": cand.get("chunk_id"),
                    "text": cand.get("chunk_text"),
                    "metadata": cand.get("metadata", {}),
                    "semantic_score": cand.get("semantic_score"),
                }
            )

        prompt = {
            "task": "select_best_point_and_summarize_change",
            "change_evidence": evidence,
            "candidates": cand_payload,
            "instructions": (
                "1) 후보 중 변화와 가장 잘 맞는 point_id를 1개 선택.\n"
                "2) 무엇이 어떻게 바뀌었는지 한 줄로 요약.\n"
                "3) 조항 내 요구사항을 bullet로 나열.\n"
                "4) 최종 신뢰도 0~1 산출. 0.7 미만이면 pending=true."
            ),
            "output_schema": {
                "selected_point_id": "string",
                "reason": "string",
                "change_summary": "string",
                "requirements": ["string"],
                "final_confidence": "float",
                "pending": "boolean",
            },
        }
        return json.dumps(prompt, ensure_ascii=False)

    async def _rerank_candidates(
        self,
        change_hint: Dict[str, Any],
        candidates: List[RetrievedChunk],
    ) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None
        prompt = self._build_rerank_prompt(change_hint, candidates)
        try:
            res = await self.llm.chat.completions.create(
                model="gpt-5-nano",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(res.choices[0].message.content)
        except Exception:
            return None

    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
        extra_filters: Optional[Dict[str, Any]] = None,
        change_query: Optional[str] = None,
    ) -> RetrievalResult:
        import asyncio

        product_id = product["product_id"]
        base_query = self._build_search_query(feature_name, feature_value, feature_unit)
        
        # 개선: Change query를 별도 검색하지 않고 결합 (1회 검색)
        if change_query:
            combined_query = f"{base_query} {change_query}"
        else:
            combined_query = base_query
        
        filters = build_product_filters(product)
        if extra_filters:
            filters.update(extra_filters)

        async def _search_once(q: str) -> RetrievalOutput:
            return await self.search_tool.search(
                query=q,
                strategy="hybrid",
                top_k=self.top_k,
                alpha=self.alpha,
                filters=filters or None,
            )

        async def _search_with_retry(q: str) -> Optional[RetrievalOutput]:
            for attempt in range(3):
                try:
                    return await _search_once(q)
                except Exception as exc:
                    if attempt < 2:
                        backoff = 0.5 * (attempt + 1)
                        logger.warning(
                            "retrieval tool 실패 retry=%d query=%s err=%s",
                            attempt + 1,
                            q,
                            exc,
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.warning("retrieval tool 최종 실패 query=%s err=%s", q, exc)
                        return None
            return None

        # run the combined query (base + change hint) once; retry on transient failures
        tool_result = await _search_with_retry(combined_query)

        if tool_result is None:
            return RetrievalResult(
                product_id=product_id,
                feature_name=feature_name,
                feature_value=feature_value,
                feature_unit=feature_unit,
                candidates=[],
            )

        def _convert(out: RetrievalOutput) -> List[RetrievedChunk]:
            converted: List[RetrievedChunk] = []
            for item in out["results"]:
                converted.append(
                    RetrievedChunk(
                        chunk_id=item.get("id", ""),
                        chunk_text=item.get("text", ""),
                        semantic_score=item.get("scores", {}).get("final_score", 0.0),
                        metadata=item.get("metadata", {}),
                    )
                )
            return converted

        candidates = _convert(tool_result)

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
        regulation_meta: Dict[str, Any] = state.get("regulation") or {}
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
        change_hint = self._choose_change_hint(change_scope)
        change_query = self._build_change_query(change_hint)
        recovered_hints: Set[str] = set()

        mapping_results: List[MappingItem] = []
        mapping_targets: Dict[str, Dict[str, Any]] = {}
        unknown_requirements: List[Dict[str, Any]] = []

        extra_search_filters = {
            key: value
            for key, value in mapping_filters.items()
            if key not in {"product_id"}
        }
        change_search_filters = self._build_change_filters(change_scope)
        regulation_filters = self._build_regulation_filters(regulation_meta)
        merged_search_filters = self._merge_filters(
            extra_search_filters, change_search_filters, regulation_filters
        )

        # ------------------------------------------------------
        # change_detection 노드에서 받은 힌트 활용 (신규 규제 분석 결과)
        # ------------------------------------------------------
        regulation_hints = state.get("regulation_analysis_hints") or {}

        if self.debug_enabled:
            logger.info(
                "🧭 Mapping start: product=%s name=%s features=%d top_k=%d alpha=%.2f",
                product_id,
                product_name,
                len(present_features),
                self.top_k,
                self.alpha,
            )
            logger.info(f"📊 change_results: {len(change_results)}개")
            logger.info(f"📊 change_scope: actionable={len(change_scope.get('actionable_results', []))}, pending={len(change_scope.get('pending_results', []))}, feature_hints={len(change_scope.get('feature_hints', set()))}")
            logger.info(f"📊 regulation_hints: {bool(regulation_hints)}")
            if not present_features:
                logger.info(
                    "💤 매핑 대상 특성이 없습니다. mapping.present_state나 target을 확인하세요."
                )
        if regulation_hints and not change_scope.get("feature_hints"):
            # 신규 규제 분석 결과에서 affected_areas를 feature_hints로 변환
            affected_areas = regulation_hints.get("affected_areas", [])
            for area in affected_areas:
                normalized = self._normalize_token(area)
                for norm_name, raw_name in {
                    self._normalize_token(name): name for name in present_features.keys()
                }.items():
                    if normalized == norm_name or normalized in norm_name:
                        recovered_hints.add(raw_name)
            
            if self.debug_enabled:
                logger.info(f"🆕 신규 규제 힌트 활용: {len(recovered_hints)}개 feature 복구")

        feature_iterable, unknown_hints = self._select_features_for_mapping(
            present_features, change_scope, recovered_hints
        )
        if self.debug_enabled:
            logger.info(
                "🔎 feature selection — hints=%s recovered=%s selected=%d",
                list(change_scope.get("feature_hints") or []),
                list(recovered_hints),
                len(feature_iterable),
            )
        if unknown_hints:
            unknown_requirements.extend(
                [
                    {
                        "hint": hint,
                        "reason": "change_detection_hint_not_in_product_features",
                    }
                    for hint in unknown_hints
                ]
            )

        # 🔥 feature별로 검색 TOOL → 매핑 (병렬 처리)
        async def process_feature(feature_name: str, present_value: Any):
            unit = units.get(feature_name)
            target_value = target_state.get(feature_name)

            # a) 검색 TOOL 호출
            if self.debug_enabled:
                logger.info(
                    "🔍 Searching feature=%s value=%s unit=%s",
                    feature_name,
                    present_value,
                    unit or "-",
                )
            retrieval: RetrievalResult = await self._run_search(
                product,
                feature_name,
                present_value,
                unit,
                merged_search_filters,
                change_query=change_query,
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

            ranked_candidates = retrieval["candidates"]
            rerank_result: Optional[Dict[str, Any]] = None
            if change_hint and ranked_candidates:
                # 규칙 기반으로 상위 3개 선택
                ranked_candidates = self._rule_rank_candidates(
                    ranked_candidates, change_hint, top_n=3
                )
                # LLM rerank로 최종 1개 선택
                rerank_result = await self._rerank_candidates(
                    change_hint, ranked_candidates
                )
                if rerank_result and rerank_result.get("selected_point_id"):
                    selected_id = rerank_result["selected_point_id"]
                    ranked_candidates = [
                        cand for cand in ranked_candidates
                        if cand.get("chunk_id") == selected_id
                    ] or ranked_candidates

            # rerank가 없거나 실패해도 중복 매핑을 피하기 위해 상위 1개만 사용
            if ranked_candidates:
                ranked_candidates = ranked_candidates[:1]

            # b) LLM 매핑 수행 (후보별 병렬)
            async def process_candidate(cand: RetrievedChunk):
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
                regulation_meta["semantic_score"] = cand.get("semantic_score")
                change_matches = self._match_change_results_to_candidate(
                    change_scope, cand
                )
                if change_matches:
                    regulation_meta["change_detection_matches"] = change_matches
                if rerank_result:
                    regulation_meta["rerank"] = rerank_result

                return MappingItem(
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
                
            
            # 후보별 병렬 처리
            import asyncio
            candidate_results = await asyncio.gather(
                *[process_candidate(cand) for cand in ranked_candidates],
                return_exceptions=True
            )
            items: List[MappingItem] = []
            for r in candidate_results:
                if isinstance(r, Exception):
                    continue
                items.append(r)
                if self.debug_enabled:
                    logger.info(
                        "🧩 applies=%s required=%s current=%s chunk=%s (%s)",
                        r["applies"],
                        r["required_value"],
                        r["current_value"],
                        r["regulation_chunk_id"],
                        r["feature_name"],
                    )
            return items
        
        # feature별 병렬 처리
        import asyncio
        feature_results = await asyncio.gather(
            *[process_feature(fname, fval) for fname, fval in feature_iterable],
            return_exceptions=True
        )
        
        # 결과 병합
        for result in feature_results:
            if isinstance(result, Exception):
                logger.error(f"❌ Feature 처리 실패: {result}")
                continue
            if isinstance(result, list):
                mapping_results.extend(result)
                for item in result:
                    if item["applies"]:
                        feature_name = item["feature_name"]
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
            actionable_changes=change_scope.get("actionable_results", []),
            pending_changes=change_scope.get("pending_results", []),
            unknown_requirements=unknown_requirements,
        )
        state["mapping"] = mapping_payload
        state["mapping_results"] = mapping_payload
        # regulation_trace 업데이트 (in-memory)
        trace_entries = self._build_trace_entries(mapping_results, regulation_meta)
        if trace_entries:
            existing_trace = product.get("regulation_trace") or {}
            existing_list = existing_trace.get("trace") or []
            last_updated = trace_entries[0]["updated_at"]
            product["regulation_trace"] = {
                "trace": existing_list + trace_entries,
                "last_updated": last_updated,
            }
            state["product_info"] = product
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
