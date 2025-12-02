# app/core/models/__init__.py

# [수정] 여기서 Base를 새로 정의하지 말고, database.py에서 가져와야 합니다.
# (경로는 프로젝트 구조에 따라 'core.database' 또는 '..database' 등 확인 필요)
from app.core.database import Base

# Import all models for Alembic
# (모델 파일들이 Base를 상속받아 정의되어 있어야 함)
from .admin_model import AdminUser
from .country_model import Country
from .product_model import Product
# ProductExportCountry 삭제
from .data_source_model import DataSource, CrawlJob, CrawlLog
from .regulation_model import (
    Regulation, 
    RegulationVersion, 
    RegulationTranslation, 
    RegulationChangeHistory,
    RegulationChangeKeynote
)
from .impact_model import ImpactScore
from .report_model import Report, ReportItem, ReportSummary
from .glossary_model import GlossaryTerm

__all__ = [
    "Base",
    "AdminUser",
    "Country",
    "Product",
    # "ProductExportCountry",
    "DataSource",
    "CrawlJob",
    "CrawlLog",
    "Regulation",
    "RegulationVersion",
    "RegulationTranslation",
    "RegulationChangeHistory",
    "RegulationChangeKeynote",
    "ImpactScore",
    "Report",
    "ReportItem",
    "ReportSummary",
    "GlossaryTerm",
]


# from sqlalchemy.orm import DeclarativeBase

# class Base(DeclarativeBase):
#     pass

# # Import all models for Alembic
# from .admin_model import AdminUser
# from .country_model import Country
# from .product_model import Product, ProductExportCountry
# from .data_source_model import DataSource, CrawlJob, CrawlLog
# from .regulation_model import (
#     Regulation, 
#     RegulationVersion, 
#     RegulationTranslation, 
#     RegulationChangeHistory,
#     RegulationChangeKeynote
# )
# from .impact_model import ImpactScore
# from .report_model import Report, ReportItem, ReportSummary
# from .glossary_model import GlossaryTerm

# __all__ = [
#     "Base",
#     "AdminUser",
#     "Country",
#     "Product",
#     "ProductExportCountry",
#     "DataSource",
#     "CrawlJob",
#     "CrawlLog",
#     "Regulation",
#     "RegulationVersion",
#     "RegulationTranslation",
#     "RegulationChangeHistory",
#     "RegulationChangeKeynote",
#     "ImpactScore",
#     "Report",
#     "ReportItem",
#     "ReportSummary",
#     "GlossaryTerm",
# ]
