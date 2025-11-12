from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from app.core.models.enums import RiskLevelEnum

class ImpactScoreBase(BaseModel):
    """영향도 점수 기본 스키마"""
    translation_id: int = Field(..., description="번역 ID")
    product_id: int = Field(..., description="제품 ID")
    impact_score: float = Field(..., ge=0.0, le=1.0, description="영향도 점수 (0.000~1.000)")
    risk_level: RiskLevelEnum = Field(..., description="위험 수준")
    
    @field_validator('impact_score')
    @classmethod
    def validate_impact_score(cls, v):
        """영향도 점수 검증 (소수점 3자리)"""
        if v < 0.0 or v > 1.0:
            raise ValueError('impact_score must be between 0.000 and 1.000')
        return round(v, 3)

class ImpactScoreCreate(ImpactScoreBase):
    """영향도 점수 생성 스키마"""
    evaluation_detail: Optional[str] = Field(None, description="평가 상세 내용")

class ImpactScoreUpdate(BaseModel):
    """영향도 점수 수정 스키마"""
    impact_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    risk_level: Optional[RiskLevelEnum] = None
    evaluation_detail: Optional[str] = None

class ImpactScoreResponse(ImpactScoreBase):
    """영향도 점수 응답 스키마"""
    impact_score_id: int
    evaluation_detail: Optional[str] = None
    evaluated_at: datetime
    
    class Config:
        from_attributes = True

class ImpactScoreWithDetails(ImpactScoreResponse):
    """상세 정보를 포함한 영향도 점수"""
    product_name: Optional[str] = None
    regulation_title: Optional[str] = None
