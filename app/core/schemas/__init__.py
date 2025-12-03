# app/core/schemas/__init__.py

from .admin_schema import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    AdminUserLogin
)

from .country_schema import (
    CountryCreate,
    CountryUpdate,
    CountryResponse,
    CountryWithRegulations
)

from .product_schema import (
    ProductCreate,
    ProductUpdate,
    ProductResponse
)

from .regulation_schema import (
    RegulationCreate,
    RegulationUpdate,
    RegulationResponse,
    RegulationVersionCreate,
    RegulationVersionResponse
)

from .report_schema import (
    ReportCreate,
    ReportResponse,
    ReportItemCreate,
    # ReportWithItemsResponse
)

from .impact_schema import (
    ImpactScoreCreate,
    ImpactScoreUpdate,
    ImpactScoreResponse,
    ImpactScoreWithDetails
)

from .data_source_schema import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    CrawlJobCreate,
    CrawlJobUpdate,
    CrawlJobResponse,
    CrawlLogCreate,
    CrawlLogResponse
)

from .glossary_schema import (
    GlossaryTermCreate,
    GlossaryTermUpdate,
    GlossaryTermResponse,
    GlossaryTermWithSynonyms
)

__all__ = [
    # Admin
    "AdminUserCreate",
    "AdminUserUpdate",
    "AdminUserResponse",
    "AdminUserLogin",
    
    # Country
    "CountryCreate",
    "CountryUpdate",
    "CountryResponse",
    "CountryWithRegulations",
    
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    
    # Regulation
    "RegulationCreate",
    "RegulationUpdate",
    "RegulationResponse",
    "RegulationVersionCreate",
    "RegulationVersionResponse",
    
    # Report
    "ReportCreate",
    "ReportResponse",
    "ReportItemCreate",
    "ReportWithItemsResponse",
    
    # Impact
    "ImpactScoreCreate",
    "ImpactScoreUpdate",
    "ImpactScoreResponse",
    "ImpactScoreWithDetails",
    
    # DataSource
    "DataSourceCreate",
    "DataSourceUpdate",
    "DataSourceResponse",
    "CrawlJobCreate",
    "CrawlJobUpdate",
    "CrawlJobResponse",
    "CrawlLogCreate",
    "CrawlLogResponse",
    
    # Glossary
    "GlossaryTermCreate",
    "GlossaryTermUpdate",
    "GlossaryTermResponse",
    "GlossaryTermWithSynonyms",
]
