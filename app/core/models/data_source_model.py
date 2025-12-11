from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from . import Base

class DataSource(Base):
    __tablename__ = "data_sources"
    
    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=True)
    
    # Relationships
    # regulations = relationship("Regulation", back_populates="data_source")

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False)
    schedule_rule = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships

class CrawlLog(Base):
    __tablename__ = "crawl_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timeline = Column(JSONB) # 12-11 DB서버는 변경 안됨
    
    # Relationships

