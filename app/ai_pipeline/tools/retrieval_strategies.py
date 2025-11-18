"""
module: retrieval_strategies.py
description: RAG 검색 전략 인터페이스 및 구현체
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - app.vectorstore.vector_client
    - app.ai_pipeline.preprocess.embedding_pipeline
    - typing, abc, logging
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """검색 결과 단일 항목."""
    
    id: str
    text: str
    scores: Dict[str, float]  # {"final_score": 0.87, "dense_score": 0.85, ...}
    metadata: Dict[str, Any]
    rank: int
    match_info: Optional[Dict[str, Any]] = None
    parent_chunk: Optional[Dict[str, Any]] = None


class RetrievalStrategy(ABC):
    """검색 전략 추상 인터페이스."""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """
        검색 실행.
        
        Args:
            query: 검색 쿼리
            filters: 메타데이터 필터
            top_k: 반환 개수
            alpha: Hybrid 가중치 (Dense 비율)
            **kwargs: 전략별 추가 파라미터
        
        Returns:
            검색 결과 리스트
        """
        pass


class DenseStrategy(RetrievalStrategy):
    """Dense Vector 검색 전략 (의미 검색)."""
    
    def __init__(self, vector_client, embedding_pipeline):
        self.vector_client = vector_client
        self.embedding_pipeline = embedding_pipeline
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """Dense 검색 실행."""
        
        # 쿼리 임베딩
        query_emb = self.embedding_pipeline.embed_single_text(query)
        
        # VectorDB 검색
        results = self.vector_client.search(
            query_dense=query_emb["dense"],
            query_sparse=None,
            top_k=top_k,
            filters=filters,
            hybrid_alpha=1.0  # Dense only
        )
        
        # 결과 변환
        return self._format_results(results, strategy="dense")
    
    def _format_results(
        self,
        raw_results: Dict[str, Any],
        strategy: str
    ) -> List[RetrievalResult]:
        """VectorClient 결과 → RetrievalResult 변환."""
        
        formatted = []
        
        for rank, (doc_id, doc_text, metadata, score) in enumerate(
            zip(
                raw_results.get("ids", []),
                raw_results.get("documents", []),
                raw_results.get("metadatas", []),
                raw_results.get("scores", [])
            ),
            start=1
        ):
            formatted.append(
                RetrievalResult(
                    id=doc_id,
                    text=doc_text,
                    scores={
                        "final_score": score,
                        "dense_score": score,
                        "sparse_score": None,
                        "hybrid_score": score
                    },
                    metadata=metadata,
                    rank=rank,
                    match_info={"strategy": strategy}
                )
            )
        
        return formatted


class HybridStrategy(RetrievalStrategy):
    """Hybrid 검색 전략 (Dense + Sparse)."""
    
    def __init__(self, vector_client, embedding_pipeline):
        self.vector_client = vector_client
        self.embedding_pipeline = embedding_pipeline
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """Hybrid 검색 실행."""
        
        # 쿼리 임베딩 (Dense + Sparse)
        query_emb = self.embedding_pipeline.embed_single_text(query)
        
        # Sparse 벡터 추출 (있으면)
        query_sparse = query_emb.get("sparse")
        
        # 디버깅: Sparse 벡터 상태 확인
        logger.debug(f"Sparse vector available: {query_sparse is not None}")
        if query_sparse:
            logger.debug(f"Sparse vector size: {len(query_sparse)}")
        
        # VectorDB 검색
        results = self.vector_client.search(
            query_dense=query_emb["dense"],
            query_sparse=query_sparse,
            top_k=top_k,
            filters=filters,
            hybrid_alpha=alpha
        )
        
        # 결과 변환
        return self._format_results(results, strategy="hybrid", alpha=alpha)
    
    def _format_results(
        self,
        raw_results: Dict[str, Any],
        strategy: str,
        alpha: float
    ) -> List[RetrievalResult]:
        """VectorClient 결과 → RetrievalResult 변환."""
        
        formatted = []
        
        for rank, (doc_id, doc_text, metadata, score) in enumerate(
            zip(
                raw_results.get("ids", []),
                raw_results.get("documents", []),
                raw_results.get("metadatas", []),
                raw_results.get("scores", [])
            ),
            start=1
        ):
            # Dense/Sparse 점수 분리 (metadata에 있으면)
            dense_score = metadata.pop("_dense_score", score)
            sparse_score = metadata.pop("_sparse_score", None)
            
            # 디버깅: 점수 확인
            logger.debug(f"Doc {doc_id}: final={score:.3f}, dense={dense_score:.3f}, sparse={sparse_score}")
            
            formatted.append(
                RetrievalResult(
                    id=doc_id,
                    text=doc_text,
                    scores={
                        "final_score": score,
                        "dense_score": dense_score,
                        "sparse_score": sparse_score,
                        "hybrid_score": score
                    },
                    metadata=metadata,
                    rank=rank,
                    match_info={
                        "strategy": strategy,
                        "alpha": alpha
                    }
                )
            )
        
        return formatted


class MetadataFirstStrategy(RetrievalStrategy):
    """메타데이터 필터 우선 전략."""
    
    def __init__(self, vector_client, embedding_pipeline):
        self.vector_client = vector_client
        self.embedding_pipeline = embedding_pipeline
        self.dense_strategy = DenseStrategy(vector_client, embedding_pipeline)
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """
        메타데이터 필터 우선 검색.
        
        1단계: 메타데이터 필터링 (필수)
        2단계: 필터된 결과에서 Dense 검색
        """
        
        if not filters:
            logger.warning("MetadataFirstStrategy: 필터 없음, Dense 검색으로 폴백")
            return await self.dense_strategy.search(query, filters, top_k, alpha)
        
        # Dense 검색 (필터 적용)
        return await self.dense_strategy.search(query, filters, top_k, alpha)


class ParentChildStrategy(RetrievalStrategy):
    """Parent-Child 검색 전략 (명제 검색 → 부모 청크 복원)."""
    
    def __init__(self, vector_client, embedding_pipeline):
        self.vector_client = vector_client
        self.embedding_pipeline = embedding_pipeline
        self.hybrid_strategy = HybridStrategy(vector_client, embedding_pipeline)
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """
        Parent-Child 검색.
        
        1단계: 명제 검색 (Hybrid)
        2단계: 부모 청크 ID 추출
        3단계: 부모 청크 복원 (VectorDB 조회)
        """
        
        # 명제 검색
        proposition_results = await self.hybrid_strategy.search(
            query, filters, top_k, alpha
        )
        
        # 부모 청크 복원
        parent_ids = set()
        for result in proposition_results:
            parent_id = result.metadata.get("meta_parent_chunk_id")
            if parent_id:
                parent_ids.add(parent_id)
        
        if not parent_ids:
            logger.warning("ParentChildStrategy: 부모 청크 ID 없음")
            return proposition_results
        
        # 부모 청크 조회 (VectorDB에서 ID로 직접 조회)
        # TODO: vector_client.get_by_ids() 메서드 구현 필요
        # 현재는 metadata에서 parent_content 사용
        
        for result in proposition_results:
            parent_id = result.metadata.get("meta_parent_chunk_id")
            parent_content = result.metadata.get("meta_parent_content", "")
            
            if parent_id:
                result.parent_chunk = {
                    "id": parent_id,
                    "text": parent_content,  # 500자 프리뷰
                    "section": result.metadata.get("meta_section"),
                    "section_title": result.metadata.get("meta_section_title")
                }
        
        return proposition_results


class HierarchicalStrategy(RetrievalStrategy):
    """계층 구조 활용 검색 전략 (Section → Proposition)."""
    
    def __init__(self, vector_client, embedding_pipeline):
        self.vector_client = vector_client
        self.embedding_pipeline = embedding_pipeline
        self.hybrid_strategy = HybridStrategy(vector_client, embedding_pipeline)
    
    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[RetrievalResult]:
        """
        계층 구조 검색.
        
        1단계: 상위 섹션 검색 (meta_section 기준)
        2단계: 해당 섹션 내 명제 검색
        3단계: 점수 재정렬
        """
        
        # 1단계: 일반 Hybrid 검색
        initial_results = await self.hybrid_strategy.search(
            query, filters, top_k * 2, alpha  # 2배 검색
        )
        
        if not initial_results:
            return []
        
        # 2단계: 섹션별 그룹핑
        section_groups = {}
        for result in initial_results:
            section = result.metadata.get("meta_section", "unknown")
            if section not in section_groups:
                section_groups[section] = []
            section_groups[section].append(result)
        
        # 3단계: 섹션별 최고 점수 기준 정렬
        section_scores = {
            section: max(r.scores["final_score"] for r in results)
            for section, results in section_groups.items()
        }
        
        sorted_sections = sorted(
            section_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 4단계: 상위 섹션의 명제들 반환
        final_results = []
        for section, _ in sorted_sections:
            section_results = section_groups[section]
            # 섹션 내 점수 순 정렬
            section_results.sort(
                key=lambda r: r.scores["final_score"],
                reverse=True
            )
            final_results.extend(section_results)
            
            if len(final_results) >= top_k:
                break
        
        # 5단계: Rank 재할당
        for rank, result in enumerate(final_results[:top_k], start=1):
            result.rank = rank
            if result.match_info:
                result.match_info["strategy"] = "hierarchical"
        
        return final_results[:top_k]


class StrategyFactory:
    """검색 전략 팩토리."""
    
    @staticmethod
    def create(
        strategy_name: str,
        vector_client,
        embedding_pipeline
    ) -> RetrievalStrategy:
        """전략 이름으로 전략 객체 생성."""
        
        strategies = {
            "dense": DenseStrategy,
            "hybrid": HybridStrategy,
<<<<<<< HEAD
            "metadata_first": MetadataFirstStrategy,
            "parent_child": ParentChildStrategy,
            "hierarchical": HierarchicalStrategy
=======
>>>>>>> 9c8d2e5de60743a693e60af5e8d67ba0c3fc7bc2
        }
        
        strategy_class = strategies.get(strategy_name.lower())
        
        if not strategy_class:
            raise ValueError(
                f"Unknown strategy: {strategy_name}. "
                f"Available: {list(strategies.keys())}"
            )
        
        return strategy_class(vector_client, embedding_pipeline)
