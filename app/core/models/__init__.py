from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import all models for Alembic
from .admin_model import AdminUser
from .country_model import Country
from .product_model import Product, ProductExportCountry
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
    "ProductExportCountry",
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