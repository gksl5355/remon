#======================================================================
# 대응 전략
# RAG로 이전 규제 대응 history 반영 
# input : 
# output : 대응 전략 3가지 str 리스트 
#======================================================================


"""
generate_strategy.py
HybridRetriever 기반 KTNG 내부 전략 추천 Node
"""

import json
from typing import Dict, List

from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from app.ai_pipeline.state import (
    StrategyItem,
    StrategyResults,
    MappingResults,
)

import logging
logger = logging.getLogger(__name__)


class StrategyNode:
    """
    규제-제품 매핑 결과를 기반으로
    내부 대응전략 DB(remon_internal_ktng)에 hybrid 검색하여
    유사 사례 전략(meta_strategy)을 추천하는 Node
    """

    def __init__(
        self,
        collection_name: str = "remon_internal_ktng",
        limit: int = 3,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        """
        Parameters
        ----------
        collection_name : Qdrant collection name
        limit : 검색 후보 개수
        dense_weight : hybrid dense 비중
        sparse_weight : hybrid sparse 비중
        """
        self.collection_name = collection_name
        self.limit = limit
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        # HybridRetriever 생성 (기본 host/port)
        self.retriever = HybridRetriever(
            default_collection=collection_name,
            host="localhost",
            port=6333,
        )

    # ----------------------------------------------------------------------
    # 1) 검색 query 생성
    # ----------------------------------------------------------------------
    def _build_query_from_mapping(self, mapping: MappingResults) -> List[str]:
        """
        MappingNode의 결과 중 regulation_summary / parsed 데이터를 활용해
        검색 query를 생성.
        """

        queries = []

        for item in mapping["items"]:
            summary = item.get("regulation_summary", "")
            parsed = item.get("parsed", {})

            # parsed 기반 쿼리 예: "nicotine limit 10mg"
            parsed_query = " ".join(
                [
                    parsed.get("category") or "",
                    parsed.get("requirement_type") or "",
                    str(item.get("required_value") or ""),
                ]
            ).strip()

            if summary:
                queries.append(summary)

            if parsed_query:
                queries.append(parsed_query)

        return queries

    # ----------------------------------------------------------------------
    # 2) KTNG 내부 전략 DB hybrid 검색
    # ----------------------------------------------------------------------
    def _search_internal_strategies(self, queries: List[str]):
        """
        Query 리스트를 기반으로 KTNG 내부 전략 데이터 hybrid 검색 수행.
        """

        all_results = []

        for q in queries:
            try:
                results = self.retriever.search(
                    query=q,
                    collection=self.collection_name,
                    limit=self.limit,
                    dense_weight=self.dense_weight,
                    sparse_weight=self.sparse_weight,
                )
                all_results.extend(results)

            except Exception as e:
                logger.warning(f"내부 전략 hybrid 검색 실패: {e}")

        return all_results[: self.limit]

    # ----------------------------------------------------------------------
    # 3) Node entrypoint
    # ----------------------------------------------------------------------
    async def run(self, state: Dict) -> Dict:
        """
        LangGraph Pipeline에서 호출되는 main entrypoint.
        MappingNode 결과를 기반으로 전략 후보를 생성한다.
        """

        mapping: MappingResults = state.get("mapping")
        if mapping is None or not mapping["items"]:
            logger.warning("mapping 결과 없음 → 전략 생성 불가")
            state["strategy"] = StrategyResults(product_id="", items=[])
            return state

        # a) 검색 query 생성
        queries = self._build_query_from_mapping(mapping)

        # b) 내부 전략 DB hybrid 검색
        results = self._search_internal_strategies(queries)

        # c) StrategyItem 생성
        strategy_items: List[StrategyItem] = []

        for r in results:
            payload = r["payload"]

            strategy_items.append(
                StrategyItem(
                    case_id=payload.get("meta_case_id") or r["id"],   # fallback → point.id
                    strategy_text=payload.get("meta_strategy") or payload.get("text") or "",  
                    regulation_text=payload.get("meta_regulation_text") or payload.get("text") or "",
                    score=r["score"],
                    products=payload.get("meta_products", []),  # 없으면 빈 리스트
                    metadata=payload,                           # payload 원본 유지
                )
            )
        
        
        # d) state 업데이트
        state["strategy"] = StrategyResults(
            product_id=mapping["product_id"],
            items=strategy_items,
        )

        return state
