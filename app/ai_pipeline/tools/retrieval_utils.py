"""
retrieval_utils.py

메타데이터 필터 빌더 및 기타 검색 관련 헬퍼.
"""

from __future__ import annotations

from typing import Any, Dict

from app.ai_pipeline.state import ProductInfo


META_COUNTRY_KEY = "meta_country"
META_CATEGORY_KEY = "meta_category"


def build_product_filters(product: ProductInfo) -> Dict[str, Any]:
    """
    제품 정보(ProductInfo)를 기반으로 Qdrant 메타데이터 필터를 생성한다.

    현재는 메타데이터 필터를 비활성화한다.
    (메타데이터 키 불일치로 검색 결과가 0건 되는 문제를 예방하기 위해)
    """

    return {}


__all__ = ["build_product_filters", "META_COUNTRY_KEY", "META_CATEGORY_KEY"]
