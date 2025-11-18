"""
module: retrieval_utils.py
description: RAG Retrieval 유틸리티 함수
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - typing, logging
"""

from typing import List, Dict, Any, Optional
import logging
from time import perf_counter

logger = logging.getLogger(__name__)


def build_product_filters(
    product: Dict[str, Any],
    global_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    제품 정보 + 글로벌 메타데이터 → 검색 필터 생성.
    
    Args:
        product: 제품 정보 (export_country, category 등)
        global_metadata: State에서 전달받은 글로벌 메타데이터
    
    Returns:
        검색 필터 딕셔너리
    
    Example:
        >>> product = {"export_country": "US", "category": "cigarette"}
        >>> filters = build_product_filters(product)
        >>> # {"meta_country": "US", "meta_regulation_type": "tobacco_control"}
    """
    filters = {}
    
    # 1. 제품 수출 국가 (최우선)
    if product.get("export_country"):
        filters["meta_country"] = product["export_country"]
    
    # 2. 제품 카테고리 → 규제 타입 매핑
    if product.get("category"):
        regulation_type = map_category_to_regulation_type(product["category"])
        if regulation_type:
            filters["meta_regulation_type"] = regulation_type
    
    # 3. 글로벌 메타데이터 병합 (State에서 전달)
    if global_metadata:
        if global_metadata.get("jurisdiction"):
            filters["meta_jurisdiction"] = global_metadata["jurisdiction"]
        
        if global_metadata.get("agency"):
            filters["meta_agency"] = global_metadata["agency"]
        
        if global_metadata.get("date_from"):
            filters["meta_date_from"] = global_metadata["date_from"]
    
    return filters


def map_category_to_regulation_type(category: str) -> Optional[str]:
    """
    제품 카테고리 → 규제 타입 매핑.
    
    Args:
        category: 제품 카테고리
    
    Returns:
        규제 타입 또는 None
    """
    mapping = {
        "cigarette": "tobacco_control",
        "e-cigarette": "tobacco_control",
        "tobacco": "tobacco_control",
        "vape": "tobacco_control",
        "medical_device": "healthcare",
        "pharmaceutical": "healthcare",
        "food": "food_safety",
        "beverage": "food_safety",
    }
    
    return mapping.get(category.lower())


def calculate_retrieval_metadata(
    strategy: str,
    filters: Optional[Dict[str, Any]],
    num_results: int,
    search_time_ms: float,
    query_text: str
) -> Dict[str, Any]:
    """
    검색 메타데이터 생성.
    
    Args:
        strategy: 검색 전략
        filters: 적용된 필터
        num_results: 결과 개수
        search_time_ms: 검색 소요 시간 (ms)
        query_text: 검색 쿼리
    
    Returns:
        메타데이터 딕셔너리
    """
    return {
        "strategy": strategy,
        "filters_applied": filters or {},
        "num_results": num_results,
        "search_time_ms": round(search_time_ms, 2),
        "query_text": query_text[:100],  # 쿼리 프리뷰
    }


def merge_retrieval_results(
    existing_results: Optional[List[Dict[str, Any]]],
    new_results: List[Dict[str, Any]],
    max_results: int = 50
) -> List[Dict[str, Any]]:
    """
    기존 검색 결과와 새 결과 병합 (중복 제거).
    
    Args:
        existing_results: 기존 결과
        new_results: 새 결과
        max_results: 최대 결과 개수
    
    Returns:
        병합된 결과
    """
    if not existing_results:
        return new_results[:max_results]
    
    # ID 기반 중복 제거
    seen_ids = {r["id"] for r in existing_results}
    merged = list(existing_results)
    
    for result in new_results:
        if result["id"] not in seen_ids:
            merged.append(result)
            seen_ids.add(result["id"])
        
        if len(merged) >= max_results:
            break
    
    return merged


def format_retrieval_result_for_state(
    result: "RetrievalResult"
) -> Dict[str, Any]:
    """
    RetrievalResult → State 저장용 딕셔너리 변환.
    
    Args:
        result: RetrievalResult 객체
    
    Returns:
        State 저장용 딕셔너리 (벡터 제외)
    """
    formatted = {
        "id": result.id,
        "rank": result.rank,
        "text": result.text,
        "scores": result.scores,
        "metadata": result.metadata,
    }
    
    if result.match_info:
        formatted["match_info"] = result.match_info
    
    if result.parent_chunk:
        formatted["parent_chunk"] = result.parent_chunk
    
    return formatted


class RetrievalTimer:
    """검색 시간 측정 컨텍스트 매니저."""
    
    def __init__(self):
        self.start_time = None
        self.elapsed_ms = 0
    
    def __enter__(self):
        self.start_time = perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (perf_counter() - self.start_time) * 1000
        return False
