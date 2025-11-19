"""
map_products.py
HybridRetriever 기반 검색 + LLM 매핑 Node
"""

import json
import logging
from typing import Any, Dict, List

from app.ai_pipeline.state import (
    ProductInfo,
    RetrievedChunk,
    RetrievalResult,
    MappingItem,
    MappingParsed,
    MappingResults,
)

from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT
from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


class MappingNode:
    """
    HybridRetriever + LLM 매핑 Node
    """

    def __init__(
        self,
        llm_client,
        top_k: int = 5,
        alpha: float = 0.7,
    ):
        self.llm = llm_client
        self.top_k = top_k
        self.alpha = alpha

        # 🔥 노드 내부에서 직접 collection 지정
        DEFAULT_COLLECTION = "remon_regulations"

        self.retriever = HybridRetriever(
            default_collection=DEFAULT_COLLECTION,
            host="localhost",
            port=6333,
        )

    # ----------------------------------------------------------------------
    # 1) HybridRetriever 검색 wrapper
    # ----------------------------------------------------------------------
    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
    ) -> RetrievalResult:

        product_id = product["product_id"]
        query = self._build_search_query(feature_name, feature_value, feature_unit)

        try:
            # HybridRetriever는 sync 함수이므로 async wrapper 필요 없음
            results = self.retriever.search(query=query, limit=self.top_k)
        except Exception as exc:
            logger.warning("HybridRetriever 검색 실패: %s", exc)
            return RetrievalResult(
                product_id=product_id,
                feature_name=feature_name,
                feature_value=feature_value,
                feature_unit=feature_unit,
                candidates=[],
            )

        # Qdrant 결과를 RetrievalResult 포맷으로 변환
        candidates: List[RetrievedChunk] = []
        for item in results:
            candidates.append(
                RetrievedChunk(
                    chunk_id=item["id"],
                    chunk_text=item["payload"].get("text", ""),
                    semantic_score=item["score"],
                    metadata=item.get("payload", {}),
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
    # 2) 프롬프트 생성
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
        parts = [str(feature_name)]
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
        product: ProductInfo = state["product_info"]
        product_id = product["product_id"]
        features = product["features"]
        units = product.get("feature_units", {})

        mapping_results: List[MappingItem] = []

        # feature 별로 검색 + LLM 매핑
        for feature_name, value in features.items():
            unit = units.get(feature_name)

            # a) HybridRetriever 검색
            retrieval: RetrievalResult = await self._run_search(
                product, feature_name, value, unit
            )

            # b) LLM 매핑
            for cand in retrieval["candidates"]:
                prompt = self._build_prompt(
                    feature_name, value, unit, cand["chunk_text"]
                )
                llm_out = await self._call_llm(prompt)

                parsed: MappingParsed = llm_out.get("parsed", {})

                mapping_results.append(
                    MappingItem(
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
                )

        # c) State 업데이트
        state["mapping"] = MappingResults(
            product_id=product_id,
            items=mapping_results,
        )

        return state
