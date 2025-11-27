from pydantic import BaseModel, Field
from typing import Optional

class CountryBase(BaseModel):
    """국가 기본 스키마"""
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO-3166-1 alpha-2 국가 코드")
    country_name: str = Field(..., min_length=1, max_length=100, description="국가명")

class CountryCreate(CountryBase):
    """국가 생성 스키마"""
    pass

class CountryUpdate(BaseModel):
    """국가 수정 스키마"""
    country_name: Optional[str] = Field(None, min_length=1, max_length=100)

class CountryResponse(CountryBase):
    """국가 응답 스키마"""
    
    class Config:
        from_attributes = True

class CountryWithRegulations(CountryResponse):
    """규제 정보를 포함한 국가 응답"""
    regulation_count: Optional[int] = Field(None, description="해당 국가의 규제 수")
