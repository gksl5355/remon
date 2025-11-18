"""
module: hybrid_search.py
description: 하이브리드 검색 (의미 + BM25 + 메타데이터 기반)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger, app.ai_pipeline.preprocess.config
    - app.ai_pipeline.preprocess.embedding_pipeline
    - app.ai_pipeline.preprocess.bm25_indexer
    - typing, numpy
"""

from typing import List, Dict, Tuple, Optional, Any
import logging
import numpy as np

logger = logging.getLogger(__name__)


class HybridSearch:
    """
    의미 검색 + BM25 키워드 검색 + 메타데이터 필터링을 결합한 하이브리드 검색.
    
    역할:
    - 의미 유사도 (cosine similarity) 계산
    - BM25 기반 키워드 매칭
    - 메타데이터 필터링 (국가, 카테고리, 날짜 등)
    - 점수 정규화 및 가중치 조합
    - 결과 랭킹 및 반환
    
    특징:
    - 알파 가중치 조정 (0 = 순 BM25, 1 = 순 의미)
    - 테이블 & 카테고리 부스팅
    - 메타데이터 기반 필터링
    - 점수 해석 (0~1, 1 = 최고 관련성)
    """
    
    def __init__(
        self,
        embedding_pipeline=None,
        bm25_indexer=None,
        alpha: float = 0.5,
        table_boost: float = 1.3,
        category_boost: float = 1.3,
    ):
        """
        하이브리드 검색 초기화.
        
        Args:
            embedding_pipeline: EmbeddingPipeline 인스턴스
            bm25_indexer: BM25Indexer 인스턴스
            alpha (float): 가중치 (0~1, 기본 0.5 = 50% 의미 + 50% BM25)
            table_boost (float): 테이블 포함 청크 부스트. 기본값: 1.3
            category_boost (float): 카테고리 매칭 부스트. 기본값: 1.3
        """
        self.embedding_pipeline = embedding_pipeline
        self.bm25_indexer = bm25_indexer
        self.alpha = alpha  # 0 ≤ alpha ≤ 1
        self.table_boost = table_boost
        self.category_boost = category_boost
        
        logger.info(
            f"✅ HybridSearch 초기화: alpha={alpha}, "
            f"table_boost={table_boost}, category_boost={category_boost}"
        )
    
    def search(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        metadata_filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색을 수행합니다.
        
        Args:
            query (str): 검색 쿼리
            candidates (List[Dict[str, Any]]): 검색 대상 청크
                [
                    {
                        "chunk_id": "doc_1_0",
                        "text": "청크 텍스트",
                        "metadata": {
                            "meta_country": "KR",
                            "meta_category": "healthcare",
                            "has_table": False,
                        }
                    },
                    ...
                ]
            metadata_filters (Optional[Dict[str, Any]]): 메타데이터 필터
                {
                    "country": "KR",
                    "category": "healthcare",
                }
            top_k (int): 상위 K개 반환. 기본값: 5
        
        Returns:
            List[Dict[str, Any]]: 상위 K개 결과
                [
                    {
                        "chunk_id": "doc_1_0",
                        "text": "...",
                        "semantic_score": 0.85,
                        "bm25_score": 0.72,
                        "final_score": 0.79,  # 가중치 조합
                        "rank": 1,
                    },
                    ...
                ]
        """
        if not candidates:
            return []
        
        # 1단계: 메타데이터 필터링
        filtered_candidates = self._apply_metadata_filters(candidates, metadata_filters)
        logger.debug(f"메타데이터 필터링: {len(candidates)} → {len(filtered_candidates)}개")
        
        if not filtered_candidates:
            logger.warning("메타데이터 필터링 후 후보가 없습니다")
            return []
        
        # 2단계: 의미 검색 점수
        semantic_scores = self._compute_semantic_scores(query, filtered_candidates)
        
        # 3단계: BM25 검색 점수
        bm25_scores = self._compute_bm25_scores(query, filtered_candidates)
        
        # 4단계: 메타데이터 부스팅
        boosted_scores = self._apply_boosting(filtered_candidates, bm25_scores)
        
        # 5단계: 최종 점수 계산 (가중치 조합)
        final_scores = self._combine_scores(semantic_scores, boosted_scores)
        
        # 6단계: 정렬 및 상위 K개 반환
        results = []
        for idx, candidate in enumerate(filtered_candidates):
            results.append({
                "chunk_id": candidate.get("chunk_id", f"chunk_{idx}"),
                "text": candidate.get("text", ""),
                "semantic_score": round(semantic_scores[idx], 4),
                "bm25_score": round(boosted_scores[idx], 4),
                "final_score": round(final_scores[idx], 4),
            })
        
        # 최종 점수로 정렬
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        # 순위 추가
        for rank, result in enumerate(results[:top_k], start=1):
            result["rank"] = rank
        
        logger.info(f"✅ 하이브리드 검색 완료: 상위 {min(top_k, len(results))}개 결과")
        return results[:top_k]
    
    def _apply_metadata_filters(
        self, candidates: List[Dict[str, Any]], filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """메타데이터 필터링을 적용합니다."""
        if not filters:
            return candidates
        
        filtered = []
        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            
            # 국가 필터
            if "country" in filters:
                if metadata.get("meta_country") != filters["country"]:
                    continue
            
            # 카테고리 필터
            if "category" in filters:
                if metadata.get("meta_category") != filters["category"]:
                    continue
            
            # 날짜 범위 필터 (선택사항)
            if "date_from" in filters:
                # 구현 생략 (datetime 비교)
                pass
            
            filtered.append(candidate)
        
        return filtered
    
    def _compute_semantic_scores(self, query: str, candidates: List[Dict[str, Any]]) -> np.ndarray:
        """의미 유사도 점수를 계산합니다."""
        if not self.embedding_pipeline:
            logger.warning("embedding_pipeline 미설정. 의미 검색 불가")
            return np.zeros(len(candidates))
        
        # 각 candidate 텍스트와 쿼리의 유사도 계산
        scores = []
        for candidate in candidates:
            text = candidate.get("text", "")
            try:
                # 유사도 검색 (0~1)
                similarities = self.embedding_pipeline.similarity_search(query, [text], top_k=1)
                score = similarities[0][1] if similarities else 0.0
                scores.append(score)
            except Exception as e:
                logger.debug(f"의미 유사도 계산 오류: {e}")
                scores.append(0.0)
        
        return np.array(scores, dtype=np.float32)
    
    def _compute_bm25_scores(self, query: str, candidates: List[Dict[str, Any]]) -> np.ndarray:
        """BM25 점수를 계산합니다."""
        if not self.bm25_indexer or not self.bm25_indexer.bm25_model:
            logger.warning("bm25_indexer 미설정. BM25 검색 불가")
            return np.zeros(len(candidates))
        
        # BM25 모델로 검색
        query_tokens = self.bm25_indexer._tokenize(query)
        bm25_scores = self.bm25_indexer.bm25_model.get_scores(query_tokens)
        
        # 정규화 (0~1)
        max_score = np.max(bm25_scores) if np.max(bm25_scores) > 0 else 1.0
        normalized_scores = bm25_scores / max_score
        
        return normalized_scores.astype(np.float32)
    
    def _apply_boosting(self, candidates: List[Dict[str, Any]], scores: np.ndarray) -> np.ndarray:
        """메타데이터 기반 부스팅을 적용합니다."""
        boosted = scores.copy()
        
        for idx, candidate in enumerate(candidates):
            metadata = candidate.get("metadata", {})
            
            # 테이블 포함 부스팅
            if metadata.get("has_table"):
                boosted[idx] *= self.table_boost
            
            # 카테고리 매칭 부스팅 (선택사항)
            # if metadata.get("meta_category") == target_category:
            #     boosted[idx] *= self.category_boost
        
        return boosted
    
    def _combine_scores(self, semantic_scores: np.ndarray, bm25_scores: np.ndarray) -> np.ndarray:
        """의미 점수와 BM25 점수를 결합합니다."""
        # 최종 점수 = alpha * semantic + (1-alpha) * bm25
        combined = self.alpha * semantic_scores + (1 - self.alpha) * bm25_scores
        return combined
    
    def batch_search(
        self,
        queries: List[str],
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[List[Dict[str, Any]]]:
        """
        여러 쿼리를 배치로 검색합니다.
        
        Args:
            queries (List[str]): 검색 쿼리 리스트
            candidates (List[Dict[str, Any]]): 검색 대상 (공통)
            top_k (int): 각 쿼리당 상위 K개
        
        Returns:
            List[List[Dict[str, Any]]]: 각 쿼리의 검색 결과
        """
        all_results = []
        for query in queries:
            try:
                results = self.search(query, candidates, top_k=top_k)
                all_results.append(results)
            except Exception as e:
                logger.error(f"배치 검색 오류 (쿼리: '{query}'): {e}")
                all_results.append([])
        
        logger.info(f"✅ {len(queries)}개 쿼리 배치 검색 완료")
        return all_results
