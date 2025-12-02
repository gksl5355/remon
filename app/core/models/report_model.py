from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from . import Base

class Report(Base):
    __tablename__ = "reports"

    report_id = Column(Integer, primary_key=True, index=True)
    created_reason = Column(String(30))
    created_at = Column(DateTime, server_default=func.now())
    file_path = Column(String(500))
    
    translation_id = Column(Integer, ForeignKey("regulation_translations.translation_id"), nullable=False)
    change_id = Column(Integer, ForeignKey("regulation_change_history.change_id"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)

    # Relationships
    translation = relationship("RegulationTranslation", back_populates="reports")
    change = relationship("RegulationChangeHistory", back_populates="reports")
    items = relationship("ReportItem", back_populates="report", cascade="all, delete-orphan")
    # [삭제됨] ReportSummary와의 관계 제거 (1:1 or 1:N 관계가 FK 삭제로 끊어짐)


class ReportItem(Base):
    __tablename__ = "report_items"

    item_id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), nullable=False)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"))
    impact_score_id = Column(Integer, ForeignKey("impact_scores.impact_score_id"))
    order_no = Column(Integer)

    # Relationships
    reports = relationship("Report", back_populates="items")
    version = relationship("RegulationVersion")
    impact_scores = relationship("ImpactScore")


class ReportSummary(Base):
    __tablename__ = "report_summaries"

    summary_id = Column(Integer, primary_key=True, index=True)
    
    # [변경] report_id, impact_score_id 제거 및 JSONB 컬럼으로 변경
    summary_text = Column(JSONB)
    
    created_at = Column(DateTime, server_default=func.now())

    # [변경] FK 제거로 인해 모든 Relationship 삭제됨