"""
module: retrieval_optimizer.py
description: Retrieval 성능 최적화 (캐싱, 배치 처리)
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - typing, asyncio, hashlib, logging
"""

from typing import List, Dict, Any, Optional, Tuple
import asyncio
import hashlib
import logging
from functools import lru_cache
from time import perf_counter

logger = logging.getLogger(__name__)


class QueryCache:
    """
    쿼리 결과 캐싱 (메모리 기반).
    
    사용 예시:
        cache = QueryCache(max_size=1000, ttl_seconds=3600)
        
        # 캐시 조회
        cached = cache.get(query, filters)
        if cached:
            return cached
        
        # 검색 실행
        results = await search(...)
        
        # 캐시 저장
        cache.set(query, filters, results)
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        캐시 초기화.
        
        Args:
            max_size: 최대 캐시 크기
            ttl_seconds: TTL (초)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_count: Dict[str, int] = {}
    
    def _generate_key(self, query: str, filters: Optional[Dict[str, Any]]) -> str:
        """캐시 키 생성 (query + filters 해시)."""
        filter_str = str(sorted(filters.items())) if filters else ""
        key_str = f"{query}:{filter_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """캐시 조회."""
        key = self._generate_key(query, filters)
        
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        
        # TTL 체크
        if perf_counter() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        
        # 접근 횟수 증가
        self._access_count[key] = self._access_count.get(key, 0) + 1
        
        logger.debug(f"캐시 히트: {key[:8]}...")
        return value
    
    def set(self, query: str, filters: Optional[Dict[str, Any]], value: Any) -> None:
        """캐시 저장."""
        key = self._generate_key(query, filters)
        
        # 캐시 크기 제한 (LRU 방식)
        if len(self._cache) >= self.max_size:
            self._evict_lru()
        
        self._cache[key] = (value, perf_counter())
        self._access_count[key] = 1
        
        logger.debug(f"캐시 저장: {key[:8]}...")
    
    def _evict_lru(self) -> None:
        """LRU 방식으로 캐시 제거."""
        if not self._access_count:
            return
        
        # 접근 횟수가 가장 적은 항목 제거
        lru_key = min(self._access_count, key=self._access_count.get)
        
        del self._cache[lru_key]
        del self._access_count[lru_key]
        
        logger.debug(f"캐시 제거 (LRU): {lru_key[:8]}...")
    
    def clear(self) -> None:
        """캐시 초기화."""
        self._cache.clear()
        self._access_count.clear()
        logger.info("캐시 초기화 완료")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "total_accesses": sum(self._access_count.values())
        }


class BatchRetriever:
    """
    배치 검색 최적화.
    
    사용 예시:
        retriever = BatchRetriever(retrieval_tool)
        
        queries = [
            {"query": "nicotine limit", "filters": {"meta_country": "US"}},
            {"query": "warning label", "filters": {"meta_country": "KR"}},
        ]
        
        results = await retriever.batch_search(queries)
    """
    
    def __init__(self, retrieval_tool, max_concurrent: int = 5):
        """
        배치 검색기 초기화.
        
        Args:
            retrieval_tool: RegulationRetrievalTool 인스턴스
            max_concurrent: 최대 동시 검색 수
        """
        self.retrieval_tool = retrieval_tool
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def batch_search(
        self,
        queries: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        배치 검색 실행.
        
        Args:
            queries: 검색 쿼리 리스트
                [
                    {"query": "...", "filters": {...}, "top_k": 5},
                    ...
                ]
            show_progress: 진행 상황 로깅
        
        Returns:
            검색 결과 리스트
        """
        tasks = []
        
        for idx, query_params in enumerate(queries):
            task = self._search_with_semaphore(idx, query_params, show_progress)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 에러 처리
        successful_results = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 검색 실패 [{idx}]: {result}")
                successful_results.append({"error": str(result)})
            else:
                successful_results.append(result)
        
        return successful_results
    
    async def _search_with_semaphore(
        self,
        idx: int,
        query_params: Dict[str, Any],
        show_progress: bool
    ) -> Dict[str, Any]:
        """세마포어를 사용한 검색 (동시 실행 제한)."""
        async with self.semaphore:
            if show_progress:
                logger.info(f"배치 검색 [{idx + 1}]: {query_params.get('query', '')[:50]}...")
            
            result = await self.retrieval_tool.search(**query_params)
            
            return {
                "query_index": idx,
                "query": query_params.get("query"),
                "results": result.results,
                "metadata": result.metadata
            }


class EmbeddingBatcher:
    """
    임베딩 배치 처리 최적화.
    
    사용 예시:
        batcher = EmbeddingBatcher(embedding_pipeline, batch_size=32)
        embeddings = await batcher.batch_embed(texts)
    """
    
    def __init__(self, embedding_pipeline, batch_size: int = 32):
        """
        임베딩 배처 초기화.
        
        Args:
            embedding_pipeline: EmbeddingPipeline 인스턴스
            batch_size: 배치 크기
        """
        self.embedding_pipeline = embedding_pipeline
        self.batch_size = batch_size
    
    async def batch_embed(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        텍스트 리스트를 배치로 임베딩.
        
        Args:
            texts: 텍스트 리스트
        
        Returns:
            임베딩 리스트 [{"dense": [...], "sparse": {...}}, ...]
        """
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # 배치 임베딩
            embeddings_result = self.embedding_pipeline.embed_texts(batch)
            
            # Dense 임베딩 추출
            dense_embeddings = embeddings_result.get("dense", [])
            sparse_embeddings = embeddings_result.get("sparse", [])
            
            # 결과 구성
            for idx, dense in enumerate(dense_embeddings):
                embedding_dict = {"dense": dense}
                
                if sparse_embeddings and idx < len(sparse_embeddings):
                    embedding_dict["sparse"] = sparse_embeddings[idx]
                
                all_embeddings.append(embedding_dict)
        
        logger.info(f"✅ 배치 임베딩 완료: {len(texts)}개 텍스트")
        return all_embeddings


@lru_cache(maxsize=128)
def cached_filter_hash(filters_tuple: Tuple) -> str:
    """필터 해시 캐싱 (불변 타입만 가능)."""
    filter_str = str(filters_tuple)
    return hashlib.md5(filter_str.encode()).hexdigest()


def optimize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    필터 최적화 (불필요한 필터 제거).
    
    Args:
        filters: 원본 필터
    
    Returns:
        최적화된 필터
    """
    optimized = {}
    
    for key, value in filters.items():
        # None 값 제거
        if value is None:
            continue
        
        # 빈 문자열 제거
        if isinstance(value, str) and not value.strip():
            continue
        
        # 빈 리스트/딕셔너리 제거
        if isinstance(value, (list, dict)) and not value:
            continue
        
        optimized[key] = value
    
    return optimized
