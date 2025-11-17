"""
map_products.py
검색 TOOL + LLM 매핑 Node
"""

import json
import logging
from typing import Any, Dict, List, Protocol, TYPE_CHECKING

from app.ai_pipeline.state import (
    ProductInfo,
    RetrievedChunk,
    RetrievalResult,
    MappingItem,
    MappingParsed,
    MappingResults,
)

from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT
from app.ai_pipeline.tools.retrieval_utils import build_product_filters


if TYPE_CHECKING:
    from app.ai_pipeline.tools.retrieval_tool import RetrievalOutput
else:
    class RetrievalOutput(Protocol):
        results: List[Dict[str, Any]]
        metadata: Dict[str, Any]


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
    ):
        self.llm = llm_client
        if search_tool is None:
            from app.ai_pipeline.tools.retrieval_tool import get_retrieval_tool

            self.search_tool = get_retrieval_tool()
        else:
            self.search_tool = search_tool
        self.top_k = top_k
        self.alpha = alpha  # 🔥 dynamic hybrid weight
        # TODO(remon-rag): replace any ad-hoc StaticRetrievalTool usage with the real
        # RegulationRetrievalTool wired to the production VectorDB/RDB once torch
        # dependencies are restored. This entry point already accepts an injected
        # search tool, so future wiring should happen in the caller (pipeline graph).

    # ----------------------------------------------------------------------
    # 1) 검색 TOOL 호출 wrapper (search_tool 인터페이스 확정되면 이 부분만 수정)
    # ----------------------------------------------------------------------
    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
    ) -> RetrievalResult:
        """
        검색 TOOL을 호출하는 wrapper.
        Hybrid 검색 Tool을 호출하고 state 스키마에 맞춰 변환한다.
        """

        product_id = product["product_id"]
        query = self._build_search_query(feature_name, feature_value, feature_unit)
        filters = build_product_filters(product)

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
        for item in tool_result.results:
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
        product: ProductInfo = state["product_info"]
        product_id = product["product_id"]
        features = product["features"]
        units = product.get("feature_units", {})

        mapping_results: List[MappingItem] = []

        # 🔥 feature별로 검색 TOOL → 매핑
        for feature_name, value in features.items():
            unit = units.get(feature_name)

            # -----------------------------------------
            # a) 검색 TOOL 호출
            # -----------------------------------------
            retrieval: RetrievalResult = await self._run_search(
                product, feature_name, value, unit
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

        # -----------------------------------------
        # c) 전역 State 업데이트
        # -----------------------------------------
        state["mapping"] = MappingResults(
            product_id=product_id,
            items=mapping_results,
        )

        return state
