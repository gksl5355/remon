"""
map_products.py
검색 TOOL(미정) + LLM 매핑 Node
search_tool의 인터페이스는 아직 결정되지 않았기 때문에
호출부는 wrapper로 감싸고 TODO로 마킹해둔다.
"""

import json
from typing import Dict, List, Any

from state import (
    ProductInfo,
    RetrievedChunk,
    RetrievalResult,
    MappingItem,
    MappingParsed,
    MappingResults,
)

from prompts.mapping_prompt import MAPPING_PROMPT


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
        self.search_tool = search_tool
        self.top_k = top_k
        self.alpha = alpha  # 🔥 dynamic hybrid weight

    # ----------------------------------------------------------------------
    # 1) 검색 TOOL 호출 wrapper (search_tool 인터페이스 확정되면 이 부분만 수정)
    # ----------------------------------------------------------------------
    async def _run_search(
        self,
        product_id: str,
        feature_name: str,
        feature_value: Any,
        feature_unit: str | None,
    ) -> RetrievalResult:
        """
        검색 TOOL을 호출하는 wrapper.
        search_tool의 최종 인터페이스가 확정되면
        이 함수만 수정하면 전체 시스템이 자동으로 연동됨.

        ✔ hybrid alpha 적용
        ✔ top_k 적용
        ✔ feature 정보 전달
        """

        # ------------------------------------------------------------------
        # 🔥 TODO(remon-ai):
        #   search_tool.py가 완성되면 아래 호출부를 해당 시그니처에 맞게 수정하세요.
        #
        #   예시 예상 형태 (완성되면 이 부분을 수정)
        #
        #   result = await self.search_tool(
        #       product_id=product_id,
        #       feature_name=feature_name,
        #       feature_value=feature_value,
        #       feature_unit=feature_unit,
        #       top_k=self.top_k,
        #       alpha=self.alpha,
        #   )
        #
        #   return RetrievalResult(**result)
        # ------------------------------------------------------------------

        # 임시 placeholder (dummy 형태)
        result = {
            "product_id": product_id,
            "feature_name": feature_name,
            "feature_value": feature_value,
            "feature_unit": feature_unit,
            "candidates": [],  # 나중에 TOOL 출력으로 채워질 것
        }

        return result

    # ----------------------------------------------------------------------
    # 2) 매핑 프롬프트 생성 (local 처리)
    # ----------------------------------------------------------------------
    def _build_prompt(self, feature_name, feature_value, feature_unit, chunk_text):
        feature = {
            "name": feature_name,
            "value": feature_value,
            "unit": feature_unit,
        }
        return MAPPING_PROMPT.format(
            feature=json.dumps(feature, ensure_ascii=False),
            chunk=chunk_text,
        )

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
                product_id, feature_name, value, unit
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
