from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base

class DataSource(Base):
    __tablename__ = "data_sources"
    
    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=True)
    
    # Relationships
    regulations = relationship("Regulation", back_populates="data_source")
    crawl_logs = relationship("CrawlLog", back_populates="data_source")

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False)
    schedule_rule = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    crawl_logs = relationship("CrawlLog", back_populates="crawl_job")

class CrawlLog(Base):
    __tablename__ = "crawl_logs"
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("crawl_jobs.job_id"), nullable=False)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    crawl_job = relationship("CrawlJob", back_populates="crawl_logs")
    data_source = relationship("DataSource", back_populates="crawl_logs")
