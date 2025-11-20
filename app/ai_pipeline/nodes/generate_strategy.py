"""
generate_strategy.py
HybridRetriever 기반 KTNG 내부 전략 추천 Node (FINAL PRODUCTION VERSION)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any

from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from app.ai_pipeline.state import (
    AppState,
    MappingResults,
    StrategyItem,
    StrategyResults,
)

logger = logging.getLogger(__name__)


# ==========================================================================
# StrategyNode Class
# ==========================================================================
class StrategyNode:
    """
    매핑 결과(MappingResults)를 기반으로 내부 전략 DB(remon_internal_ktng)를
    HybridRetriever로 검색하여 StrategyItem 리스트를 생성한다.
    """

    def __init__(
        self,
        collection_name: str = "remon_internal_ktng",
        limit: int = 3,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        self.collection_name = collection_name
        self.limit = limit
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        self.retriever = HybridRetriever(
            default_collection=collection_name,
            host="localhost",
            port=6333,
        )

    # ----------------------------------------------------------------------
    # Query builder
    # ----------------------------------------------------------------------
    def _build_queries(self, mapping: MappingResults) -> List[str]:
        """
        매핑 결과의 regulation_summary 및 parsed 정보를 사용하여
        검색용 query를 생성한다.
        """

        queries = []

        for item in mapping["items"]:
            summary = item.get("regulation_summary", "")

            parsed = item.get("parsed", {})
            parsed_query = " ".join(
                filter(
                    None,
                    [
                        parsed.get("category"),
                        parsed.get("requirement_type"),
                        str(item.get("required_value")),
                    ],
                )
            )

            if summary:
                queries.append(summary)

            if parsed_query:
                queries.append(parsed_query)

        return queries

    # ----------------------------------------------------------------------
    # Search internal strategy DB
    # ----------------------------------------------------------------------
    def _search_internal(self, queries: List[str]):
        """HybridRetriever로 내부 전략 DB를 검색한다."""

        all_results = []

        for q in queries:
            try:
                res = self.retriever.search(
                    query=q,
                    collection=self.collection_name,
                    limit=self.limit,
                    dense_weight=self.dense_weight,
                    sparse_weight=self.sparse_weight,
                )
                all_results.extend(res)
            except Exception as e:
                logger.warning(f"[StrategyNode] 검색 실패: {e}")

        return all_results[: self.limit]

    # ----------------------------------------------------------------------
    # StrategyItem 생성기
    # ----------------------------------------------------------------------
    def _convert_to_items(self, results: List[Dict[str, Any]]) -> List[StrategyItem]:
        """
        Qdrant 검색 결과(payload)의 구조를 StrategyItem 스키마로 변환한다.
        state.py 기준 필드:
            feature_name: str
            regulation_chunk_id: str
            impact_level: str
            summary: str
            recommendation: str
        """

        items: List[StrategyItem] = []

        for r in results:
            payload = r.get("payload", {})

            items.append(
                StrategyItem(
                    feature_name=payload.get("feature_name", "GENERAL"),
                    regulation_chunk_id=str(payload.get("chunk_id", "")),
                    impact_level=payload.get("impact_level", "medium"),
                    summary=payload.get("meta_strategy", "") or payload.get("text", ""),
                    recommendation=payload.get("recommendation", ""),
                )
            )

        return items

    # ----------------------------------------------------------------------
    # Main entrypoint for LangGraph
    # ----------------------------------------------------------------------
    async def run(self, state: AppState) -> AppState:

        mapping: MappingResults = state.get("mapping")
        if not mapping or not mapping.get("items"):
            logger.warning("[StrategyNode] mapping 결과 없음, strategy 생성 불가")
            state["strategy"] = StrategyResults(product_id="", items=[])
            return state

        # 1) Query 생성
        queries = self._build_queries(mapping)

        # 2) 내부 전략 검색
        results = self._search_internal(queries)

        # 3) StrategyItem 변환
        items = self._convert_to_items(results)

        # 4) state 업데이트
        state["strategy"] = StrategyResults(
            product_id=mapping["product_id"],
            items=items,
        )

        return state


# ==========================================================================
# LangGraph에서 직접 사용하는 Node 함수
# ==========================================================================
strategy_node_instance = StrategyNode()


async def generate_strategy_node(state: AppState) -> AppState:
    """LangGraph pipeline에서 호출되는 wrapper 함수"""
    return await strategy_node_instance.run(state)
