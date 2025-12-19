from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Report(Base):
    """리포트 메인 테이블"""
    __tablename__ = "reports"

    report_id = Column(Integer, primary_key=True, index=True)
    created_reason = Column(String(30))
    created_at = Column(DateTime, server_default=func.now())
    file_path = Column(String(500)) # 로컬 경로 (기존)
    
    # [신규] S3 Key 및 PDF 업데이트 시간
    s3_key = Column(String(500), nullable=True)
    pdf_updated_at = Column(DateTime, nullable=True)

    translation_id = Column(Integer, ForeignKey("regulation_translations.translation_id"), nullable=False)
    change_id = Column(Integer, ForeignKey("regulation_change_history.change_id"))
    product_id = Column(Integer, ForeignKey("products.product_id"))
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)


class ReportItem(Base):
    """리포트 항목 테이블"""
    __tablename__ = "report_items"
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    report = relationship("Report", back_populates="items")


class ReportSummary(Base):
    """리포트 요약 테이블 (JSONB 저장)"""
    __tablename__ = "report_summaries"
    
    summary_id = Column(Integer, primary_key=True, autoincrement=True)
    summary_text = Column(JSONB, nullable=False)
    translation = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
