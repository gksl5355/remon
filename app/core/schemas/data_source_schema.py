from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional

# ========== DataSource Schemas ==========

class DataSourceBase(BaseModel):
    """데이터 소스 기본 스키마"""
    source_name: str = Field(..., min_length=1, max_length=100, description="소스명")
    url: str = Field(..., max_length=500, description="소스 URL")
    source_type: Optional[str] = Field(None, max_length=50, description="소스 타입")

class DataSourceCreate(DataSourceBase):
    """데이터 소스 생성 스키마"""
    pass

class DataSourceUpdate(BaseModel):
    """데이터 소스 수정 스키마"""
    source_name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    source_type: Optional[str] = Field(None, max_length=50)

class DataSourceResponse(DataSourceBase):
    """데이터 소스 응답 스키마"""
    source_id: int
    
    class Config:
        from_attributes = True

# ========== CrawlJob Schemas ==========

class CrawlJobBase(BaseModel):
    """크롤링 작업 기본 스키마"""
    job_name: str = Field(..., min_length=1, max_length=100, description="작업명")
    schedule_rule: Optional[str] = Field(None, max_length=100, description="스케줄 규칙 (cron 형식)")
    is_active: bool = Field(True, description="활성 상태")

class CrawlJobCreate(CrawlJobBase):
    """크롤링 작업 생성 스키마"""
    pass

class CrawlJobUpdate(BaseModel):
    """크롤링 작업 수정 스키마"""
    job_name: Optional[str] = Field(None, min_length=1, max_length=100)
    schedule_rule: Optional[str] = None
    is_active: Optional[bool] = None

class CrawlJobResponse(CrawlJobBase):
    """크롤링 작업 응답 스키마"""
    job_id: int
    
    class Config:
        from_attributes = True

# ========== CrawlLog Schemas ==========

class CrawlLogBase(BaseModel):
    """크롤링 로그 기본 스키마"""
    job_id: int = Field(..., description="작업 ID")
    source_id: int = Field(..., description="소스 ID")
    status: str = Field(..., max_length=50, description="상태 (success, failed, running)")

class CrawlLogCreate(CrawlLogBase):
    """크롤링 로그 생성 스키마"""
    pass

class CrawlLogResponse(CrawlLogBase):
    """크롤링 로그 응답 스키마"""
    log_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class CrawlLogWithDetails(CrawlLogResponse):
    """상세 정보를 포함한 크롤링 로그"""
    job_name: Optional[str] = None
    source_name: Optional[str] = None
