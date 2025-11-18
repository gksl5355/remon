"""
module: retrieval_tool.py
description: LangChain 호환 RAG Retrieval Tool
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - langchain.tools.BaseTool
    - app.vectorstore.vector_client
    - app.ai_pipeline.preprocess.embedding_pipeline
    - app.ai_pipeline.tools.retrieval_strategies
    - app.ai_pipeline.tools.retrieval_config
    - app.ai_pipeline.tools.retrieval_utils
"""

from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field
import logging

from app.vectorstore.vector_client import VectorClient
from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
from app.ai_pipeline.tools.retrieval_strategies import StrategyFactory, RetrievalResult
from app.ai_pipeline.tools.retrieval_config import RetrievalConfig, MetadataFilter
from app.ai_pipeline.tools.retrieval_utils import (
    calculate_retrieval_metadata,
    format_retrieval_result_for_state,
    RetrievalTimer,
)

logger = logging.getLogger(__name__)


class RetrievalInput(BaseModel):
    """Retrieval Tool 입력 스키마."""

    query: str = Field(description="검색 쿼리 (제품명, 규제 내용 등)")
    strategy: str = Field(
        default="hybrid",
        description="검색 전략: dense, hybrid, metadata_first, parent_child",
    )
    top_k: int = Field(default=5, description="반환할 결과 개수")
    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="메타데이터 필터 (meta_country, meta_jurisdiction 등)"
    )
    alpha: float = Field(default=0.7, description="Hybrid 검색 시 Dense 가중치 (0~1)")
    return_parent: bool = Field(
        default=False, description="명제 검색 시 부모 청크 반환 여부"
    )


class RetrievalOutput(BaseModel):
    """Retrieval Tool 출력 스키마."""

    results: List[Dict[str, Any]] = Field(description="검색 결과 리스트")
    metadata: Dict[str, Any] = Field(description="검색 메타정보")


class RegulationRetrievalTool:
    """
    규제 문서 VectorDB 검색 Tool (LangChain 호환).

    사용 예시:
        tool = RegulationRetrievalTool()
        result = await tool.search(
            query="nicotine content limit",
            strategy="hybrid",
            filters={"meta_country": "US"}
        )
    """

    name = "regulation_retrieval"
    description = """
    규제 문서 VectorDB에서 관련 컨텍스트를 검색합니다.
    
    사용 시나리오:
    - 제품 매핑: "nicotine content limit tobacco products"
    - 영향도 평가: "warning label requirements cigarettes"
    - 전략 생성: "FDA enforcement actions tobacco violations"
    
    지원 기능:
    - Dense/Hybrid 검색 (의미 + 키워드)
    - 메타데이터 필터링 (국가, 규제 타입, 날짜 등)
    - Parent-Child 복원 (명제 → 전체 청크)
    """

    def __init__(
        self,
        vector_client: Optional[VectorClient] = None,
        embedding_pipeline: Optional[EmbeddingPipeline] = None,
        config: Optional[RetrievalConfig] = None,
    ):
        """
        Tool 초기화.

        Args:
            vector_client: Qdrant 클라이언트 (None이면 자동 생성)
            embedding_pipeline: 임베딩 파이프라인 (None이면 자동 생성)
            config: Tool 설정 (None이면 기본값)
        """
        self.vector_client = vector_client or VectorClient()
        self.embedding_pipeline = embedding_pipeline or EmbeddingPipeline(
            use_sparse=True
        )
        self.config = config or RetrievalConfig.from_settings()

        logger.info(
            f"✅ RegulationRetrievalTool 초기화: strategy={self.config.default_strategy}"
        )

    async def search(
        self,
        query: str,
        strategy: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        alpha: Optional[float] = None,
        return_parent: Optional[bool] = None,
    ) -> RetrievalOutput:
        """
        검색 실행 (비동기).

        Args:
            query: 검색 쿼리
            strategy: 검색 전략 (None이면 config 기본값)
            top_k: 반환 개수 (None이면 config 기본값)
            filters: 메타데이터 필터
            alpha: Hybrid 가중치 (None이면 config 기본값)
            return_parent: 부모 청크 반환 여부 (None이면 config 기본값)

        Returns:
            RetrievalOutput (results + metadata)
        """
        # 기본값 적용
        strategy = strategy or self.config.default_strategy
        top_k = top_k or self.config.default_top_k
        alpha = alpha if alpha is not None else self.config.default_alpha
        return_parent = (
            return_parent
            if return_parent is not None
            else self.config.return_parent_by_default
        )

        # Parent-Child 전략 강제 적용
        if return_parent and strategy != "parent_child":
            logger.info(f"return_parent=True, 전략 변경: {strategy} → parent_child")
            strategy = "parent_child"

        # 검색 실행
        with RetrievalTimer() as timer:
            # 전략 선택
            strategy_impl = StrategyFactory.create(
                strategy, self.vector_client, self.embedding_pipeline
            )

            # 검색
            results = await strategy_impl.search(
                query=query, filters=filters, top_k=top_k, alpha=alpha
            )

        # 결과 포맷팅
        formatted_results = [format_retrieval_result_for_state(r) for r in results]

        # 메타데이터 생성
        metadata = calculate_retrieval_metadata(
            strategy=strategy,
            filters=filters,
            num_results=len(results),
            search_time_ms=timer.elapsed_ms,
            query_text=query,
        )

        if self.config.log_search_metadata:
            logger.info(
                f"🔍 검색 완료: strategy={strategy}, results={len(results)}, "
                f"time={timer.elapsed_ms:.1f}ms"
            )

        return RetrievalOutput(results=formatted_results, metadata=metadata)

    def search_sync(
        self,
        query: str,
        strategy: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        alpha: Optional[float] = None,
        return_parent: Optional[bool] = None,
    ) -> RetrievalOutput:
        """
        검색 실행 (동기, 비권장).

        비동기 환경이 아닐 때만 사용.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.search(query, strategy, top_k, filters, alpha, return_parent)
        )

    def build_filters_from_product(
        self, product: Dict[str, Any], global_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        제품 정보로부터 검색 필터 생성.

        Args:
            product: 제품 정보 (export_country, category 등)
            global_metadata: State 메타데이터

        Returns:
            검색 필터
        """
        from app.ai_pipeline.tools.retrieval_utils import build_product_filters

        return build_product_filters(product, global_metadata)


# 싱글톤 인스턴스 (노드에서 재사용)
_default_tool_instance: Optional[RegulationRetrievalTool] = None


def get_retrieval_tool(
    vector_client: Optional[VectorClient] = None,
    embedding_pipeline: Optional[EmbeddingPipeline] = None,
    config: Optional[RetrievalConfig] = None,
) -> RegulationRetrievalTool:
    """
    Retrieval Tool 싱글톤 인스턴스 반환.

    Args:
        vector_client: VectorClient (None이면 기본값)
        embedding_pipeline: EmbeddingPipeline (None이면 기본값)
        config: RetrievalConfig (None이면 기본값)

    Returns:
        RegulationRetrievalTool 인스턴스
    """
    global _default_tool_instance

    if _default_tool_instance is None:
        _default_tool_instance = RegulationRetrievalTool(
            vector_client=vector_client,
            embedding_pipeline=embedding_pipeline,
            config=config,
        )

    return _default_tool_instance
