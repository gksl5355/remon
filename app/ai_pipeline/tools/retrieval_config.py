"""
module: retrieval_config.py
description: RAG Retrieval Tool 설정 관리
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - app.config.settings
    - dataclasses, typing
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetadataFilter:
    """
    VectorDB 검색 시 적용할 메타데이터 필터.

    사용 예시:
        filter = MetadataFilter(country="US", jurisdiction="federal")
        results = retrieval_tool.search(query="...", filters=filter.to_dict())
    """

    # 국가 필터
    country: Optional[str] = None  # "KR", "US", "EU"

    # 관할권 필터
    jurisdiction: Optional[str] = None  # "federal", "state", "local"

    # 규제 기관
    agency: Optional[str] = None  # "FDA", "State Board", "Local Health Dept"

    # 법률 유형
    law_type: Optional[str] = None  # "statute", "code", "regulation", "rule"

    # 규제 카테고리
    regulation_type: Optional[str] = (
        None  # "tobacco_control", "healthcare", "food_safety"
    )

    # 날짜 범위
    date_from: Optional[str] = None  # ISO format: "2025-01-01"
    date_to: Optional[str] = None

    # 계층 구조
    section: Optional[str] = None  # "SEC. 101"
    has_table: Optional[bool] = None

    # CFR 인용
    cfr_citation: Optional[str] = None  # "21 CFR § 1160.10"

    # 추가 커스텀 필터
    custom_filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """필터를 딕셔너리로 변환 (None 값 제외)."""
        filters = {}

        if self.country:
            filters["meta_country"] = self.country
        if self.jurisdiction:
            filters["meta_jurisdiction"] = self.jurisdiction
        if self.agency:
            filters["meta_agency"] = self.agency
        if self.law_type:
            filters["meta_law_type"] = self.law_type
        if self.regulation_type:
            filters["meta_regulation_type"] = self.regulation_type
        if self.date_from:
            filters["meta_date_from"] = self.date_from
        if self.date_to:
            filters["meta_date_to"] = self.date_to
        if self.section:
            filters["meta_section"] = self.section
        if self.has_table is not None:
            filters["meta_has_table"] = self.has_table
        if self.cfr_citation:
            filters["meta_cfr_citation"] = self.cfr_citation

        # 커스텀 필터 병합
        filters.update(self.custom_filters)

        return filters

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetadataFilter":
        """딕셔너리에서 필터 생성."""
        return cls(
            country=data.get("meta_country"),
            jurisdiction=data.get("meta_jurisdiction"),
            agency=data.get("meta_agency"),
            law_type=data.get("meta_law_type"),
            regulation_type=data.get("meta_regulation_type"),
            date_from=data.get("meta_date_from"),
            date_to=data.get("meta_date_to"),
            section=data.get("meta_section"),
            has_table=data.get("meta_has_table"),
            cfr_citation=data.get("meta_cfr_citation"),
            custom_filters={
                k: v
                for k, v in data.items()
                if k.startswith("meta_")
                and k
                not in [
                    "meta_country",
                    "meta_jurisdiction",
                    "meta_agency",
                    "meta_law_type",
                    "meta_regulation_type",
                    "meta_date_from",
                    "meta_date_to",
                    "meta_section",
                    "meta_has_table",
                    "meta_cfr_citation",
                ]
            },
        )


@dataclass
class RetrievalConfig:
    """
    Retrieval Tool 전역 설정.

    사용 예시:
        config = RetrievalConfig.from_settings()
        tool = RegulationRetrievalTool(config=config)
    """

    # 검색 설정
    default_strategy: str = (
        "hybrid"  # "dense", "sparse", "hybrid", "metadata_first", "parent_child"
    )
    default_top_k: int = 5
    default_alpha: float = 0.7  # Hybrid 검색 시 Dense 가중치 (0~1)

    # Parent-Child 설정
    return_parent_by_default: bool = False
    parent_content_max_chars: int = 500  # 부모 청크 프리뷰 길이

    # 성능 설정
    enable_caching: bool = False  # Redis 캐싱 (추후 구현)
    cache_ttl_seconds: int = 3600

    # 디버깅
    verbose: bool = False
    log_search_metadata: bool = True

    @classmethod
    def from_settings(cls) -> "RetrievalConfig":
        """app.config.settings에서 설정 로드."""
        try:
            from app.config.settings import settings

            return cls(
                default_top_k=getattr(settings, "MAPPING_TOP_K", 5),
                default_alpha=getattr(settings, "MAPPING_ALPHA", 0.7),
                verbose=False,
                log_search_metadata=True,
            )
        except ImportError:
            logger.warning("settings 로드 실패, 기본값 사용")
            return cls()

    def validate(self) -> None:
        """설정 유효성 검증."""
        if not (0 <= self.default_alpha <= 1):
            raise ValueError(f"alpha must be between 0 and 1, got {self.default_alpha}")

        if self.default_top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {self.default_top_k}")

        valid_strategies = {
            "dense",
            "sparse",
            "hybrid",
            "metadata_first",
            "parent_child",
        }
        if self.default_strategy not in valid_strategies:
            raise ValueError(f"Invalid strategy: {self.default_strategy}")
