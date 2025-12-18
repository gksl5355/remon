"""
module: report_model.py
description: 리포트 관련 SQLAlchemy 모델
author: AI Agent
created: 2025-01-22
updated: 2025-01-22
dependencies:
    - sqlalchemy
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class Report(Base):
    """리포트 메인 테이블"""
    __tablename__ = "reports"
    
    report_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    items = relationship("ReportItem", back_populates="report")


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
