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

    현재는 제품의 수출 국가와 카테고리를 규제 청크 메타데이터의
    ``meta_country`` / ``meta_category`` 필드에 매핑한다.
    추후 더 많은 필터 조건이 필요해지면 이 함수만 확장하면 된다.
    """

    filters: Dict[str, Any] = {}

    export_country = product.get("export_country")
    if export_country:
        filters[META_COUNTRY_KEY] = export_country

    category = product.get("category")
    if category:
        filters[META_CATEGORY_KEY] = category

    return filters


__all__ = ["build_product_filters", "META_COUNTRY_KEY", "META_CATEGORY_KEY"]
