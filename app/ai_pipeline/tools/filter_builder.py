"""
module: filter_builder.py
description: 동적 메타데이터 필터 빌더
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - typing, logging
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FilterBuilder:
    """
    동적 메타데이터 필터 생성 빌더.
    
    사용 예시:
        builder = FilterBuilder()
        filters = (builder
            .with_country("US")
            .with_jurisdiction("federal")
            .with_date_range(days_ago=365)
            .build())
    """
    
    def __init__(self):
        self._filters: Dict[str, Any] = {}
    
    def with_country(self, country: str) -> "FilterBuilder":
        """국가 필터 추가."""
        if country:
            self._filters["meta_country"] = country.upper()
        return self
    
    def with_jurisdiction(self, jurisdiction: str) -> "FilterBuilder":
        """관할권 필터 추가."""
        if jurisdiction:
            self._filters["meta_jurisdiction"] = jurisdiction.lower()
        return self
    
    def with_agency(self, agency: str) -> "FilterBuilder":
        """규제 기관 필터 추가."""
        if agency:
            self._filters["meta_agency"] = agency
        return self
    
    def with_law_type(self, law_type: str) -> "FilterBuilder":
        """법률 유형 필터 추가."""
        if law_type:
            self._filters["meta_law_type"] = law_type.lower()
        return self
    
    def with_regulation_type(self, regulation_type: str) -> "FilterBuilder":
        """규제 카테고리 필터 추가."""
        if regulation_type:
            self._filters["meta_regulation_type"] = regulation_type.lower()
        return self
    
    def with_section(self, section: str) -> "FilterBuilder":
        """섹션 필터 추가."""
        if section:
            self._filters["meta_section"] = section
        return self
    
    def with_has_table(self, has_table: bool) -> "FilterBuilder":
        """테이블 포함 여부 필터 추가."""
        self._filters["meta_has_table"] = has_table
        return self
    
    def with_date_range(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        days_ago: Optional[int] = None
    ) -> "FilterBuilder":
        """
        날짜 범위 필터 추가.
        
        Args:
            date_from: 시작 날짜 (ISO format)
            date_to: 종료 날짜 (ISO format)
            days_ago: N일 전부터 (date_from 대신 사용)
        """
        if days_ago:
            date_from = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        
        if date_from:
            self._filters["meta_date_from"] = date_from
        
        if date_to:
            self._filters["meta_date_to"] = date_to
        
        return self
    
    def with_custom(self, key: str, value: Any) -> "FilterBuilder":
        """커스텀 필터 추가."""
        if key and value is not None:
            self._filters[key] = value
        return self
    
    def merge(self, other_filters: Dict[str, Any]) -> "FilterBuilder":
        """다른 필터 딕셔너리 병합."""
        if other_filters:
            self._filters.update(other_filters)
        return self
    
    def build(self) -> Dict[str, Any]:
        """필터 딕셔너리 반환."""
        return self._filters.copy()
    
    def reset(self) -> "FilterBuilder":
        """필터 초기화."""
        self._filters.clear()
        return self


class ProductFilterBuilder(FilterBuilder):
    """
    제품 정보 기반 필터 빌더 (확장).
    
    사용 예시:
        builder = ProductFilterBuilder()
        filters = builder.from_product(product_data).build()
    """
    
    def from_product(
        self,
        product: Dict[str, Any],
        global_metadata: Optional[Dict[str, Any]] = None
    ) -> "ProductFilterBuilder":
        """
        제품 정보로부터 필터 자동 생성.
        
        Args:
            product: 제품 정보 (export_country, category 등)
            global_metadata: State 메타데이터
        """
        # 제품 수출 국가
        if product.get("export_country"):
            self.with_country(product["export_country"])
        
        # 제품 카테고리 → 규제 타입
        if product.get("category"):
            regulation_type = self._map_category(product["category"])
            if regulation_type:
                self.with_regulation_type(regulation_type)
        
        # 글로벌 메타데이터 병합
        if global_metadata:
            if global_metadata.get("jurisdiction"):
                self.with_jurisdiction(global_metadata["jurisdiction"])
            
            if global_metadata.get("agency"):
                self.with_agency(global_metadata["agency"])
            
            if global_metadata.get("date_from"):
                self.with_date_range(date_from=global_metadata["date_from"])
        
        return self
    
    def _map_category(self, category: str) -> Optional[str]:
        """제품 카테고리 → 규제 타입 매핑."""
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


class AdvancedFilterBuilder(FilterBuilder):
    """
    고급 필터 빌더 (복합 조건).
    
    사용 예시:
        builder = AdvancedFilterBuilder()
        filters = (builder
            .with_any_of_countries(["US", "KR"])
            .with_recent_regulations(days=180)
            .exclude_sections(["SEC. 999"])
            .build())
    """
    
    def with_any_of_countries(self, countries: List[str]) -> "AdvancedFilterBuilder":
        """여러 국가 중 하나 (OR 조건)."""
        if countries:
            # Qdrant는 OR 조건을 should로 처리
            self._filters["meta_country_any"] = [c.upper() for c in countries]
        return self
    
    def with_recent_regulations(self, days: int = 365) -> "AdvancedFilterBuilder":
        """최근 N일 이내 규제만."""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        self.with_date_range(date_from=date_from)
        return self
    
    def exclude_sections(self, sections: List[str]) -> "AdvancedFilterBuilder":
        """특정 섹션 제외."""
        if sections:
            self._filters["meta_section_exclude"] = sections
        return self
    
    def with_priority_agencies(self, agencies: List[str]) -> "AdvancedFilterBuilder":
        """우선 규제 기관."""
        if agencies:
            self._filters["meta_agency_priority"] = agencies
        return self


def create_filter_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    AppState 메타데이터로부터 필터 생성.
    
    Args:
        state: AppState 딕셔너리
    
    Returns:
        필터 딕셔너리
    """
    metadata = state.get("metadata", {})
    
    builder = FilterBuilder()
    
    if metadata.get("country"):
        builder.with_country(metadata["country"])
    
    if metadata.get("jurisdiction"):
        builder.with_jurisdiction(metadata["jurisdiction"])
    
    if metadata.get("agency"):
        builder.with_agency(metadata["agency"])
    
    if metadata.get("regulation_type"):
        builder.with_regulation_type(metadata["regulation_type"])
    
    return builder.build()
