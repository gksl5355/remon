"""
retrieval_tool.py

LangGraph map_products 노드에서 사용할 규제 검색 Tool.
HybridRetriever(Qdrant) 기반 하이브리드 검색을 감싼 비동기 래퍼를 제공한다.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urlparse

from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from app.config.settings import settings


class RetrievalItem(TypedDict):
    """검색 결과 아이템 스키마."""

    id: str
    text: str
    metadata: Dict[str, Any]
    scores: Dict[str, float]


class RetrievalOutput(TypedDict):
    """검색 결과 컨테이너."""

    results: List[RetrievalItem]
    metadata: Dict[str, Any]


class RegulationRetrievalTool:
    """
    HybridRetriever 기반 규제 검색 Tool.

    LangGraph 노드에서는 비동기 search() 메서드만 호출하면 되고,
    내부에서는 run_in_executor 로 Qdrant 검색을 실행한다.
    """

    def __init__(
        self,
        *,
        collection: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        retriever: Optional[HybridRetriever] = None,
    ):
        parsed = urlparse(settings.QDRANT_URL)
        resolved_host = host or parsed.hostname or "localhost"
        resolved_port = port or parsed.port or 6333
        self.collection = collection or settings.QDRANT_COLLECTION
        self._retriever = retriever or HybridRetriever(
            default_collection=self.collection,
            host=resolved_host,
            port=resolved_port,
        )

    async def search(
        self,
        *,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        alpha: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalOutput:
        """
        하이브리드 검색 실행.

        Parameters
        ----------
        query : str
            검색 쿼리
        strategy : str
            현재는 "hybrid"만 지원 (호환성 유지를 위해 파라미터만 둔다)
        top_k : int
            결과 개수
        alpha : float
            dense 가중치(0~1). sparse 가중치는 (1-alpha)
        filters : Optional[Dict[str, Any]]
            Qdrant 메타데이터 필터
        """
        if strategy != "hybrid":
            raise ValueError("현재는 hybrid 전략만 지원합니다.")

        dense_weight = max(0.0, min(1.0, alpha))
        sparse_weight = 1.0 - dense_weight

        loop = asyncio.get_running_loop()
        search_coro = partial(
            self._retriever.search,
            query=query,
            collection=self.collection,
            limit=top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            filters=filters,
        )
        raw_results = await loop.run_in_executor(None, search_coro)

        formatted: List[RetrievalItem] = []
        for item in raw_results:
            payload = item.get("payload") or {}
            formatted.append(
                RetrievalItem(
                    id=str(item.get("id")),
                    text=item.get("text") or payload.get("text", ""),
                    metadata=payload,
                    scores=item.get("scores")
                    or {"final_score": item.get("score", 0.0)},
                )
            )

        return RetrievalOutput(
            results=formatted,
            metadata={
                "query": query,
                "top_k": top_k,
                "alpha": dense_weight,
                "filters": filters or {},
            },
        )


_DEFAULT_TOOL: Optional[RegulationRetrievalTool] = None


def get_retrieval_tool() -> RegulationRetrievalTool:
    """Map node에서 사용할 기본 Tool 싱글톤."""
    global _DEFAULT_TOOL
    if _DEFAULT_TOOL is None:
        _DEFAULT_TOOL = RegulationRetrievalTool()
    return _DEFAULT_TOOL


__all__ = [
    "RegulationRetrievalTool",
    "RetrievalOutput",
    "RetrievalItem",
    "get_retrieval_tool",
]
