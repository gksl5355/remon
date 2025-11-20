from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base

class Report(Base):
    __tablename__ = "reports"
    
    report_id = Column(Integer, primary_key=True, autoincrement=True)
    created_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String(500), nullable=True)
    translation_id = Column(Integer, ForeignKey("regulation_translations.translation_id"), nullable=False)
    change_id = Column(Integer, ForeignKey("regulation_change_history.change_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)
    
    # Relationships
    items = relationship("ReportItem", back_populates="report", cascade="all, delete-orphan")
    summaries = relationship("ReportSummary", back_populates="report", cascade="all, delete-orphan")

class ReportItem(Base):
    __tablename__ = "report_items"
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), nullable=False)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    impact_score_id = Column(Integer, ForeignKey("impact_scores.impact_score_id"), nullable=False)
    order_no = Column(Integer, nullable=False)
    
    # Relationships
    report = relationship("Report", back_populates="items")
    regulation_version = relationship("RegulationVersion", back_populates="report_items")

class ReportSummary(Base):
    __tablename__ = "report_summaries"
    
    summary_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), nullable=False)
    impact_score_id = Column(Integer, ForeignKey("impact_scores.impact_score_id"), nullable=False)
    # summary_text = Column(Text, nullable=True)  # 기존 마크다운 (deprecated)
    summary_text = Column(JSONB, nullable=True)  # 새로운 JSON 형식
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    report = relationship("Report", back_populates="summaries")
    impact_score = relationship("ImpactScore", back_populates="report_summaries")
