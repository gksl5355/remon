from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class RegulationBase(BaseModel):
    source_id: int
    country_code: str
    external_id: Optional[str] = None
    title: Optional[str] = None
    language: Optional[str] = None
    status: Optional[str] = None

class RegulationCreate(RegulationBase):
    proclaimed_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None

class RegulationUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[datetime] = None

class RegulationResponse(RegulationBase):
    regulation_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class RegulationVersionCreate(BaseModel):
    regulation_id: int
    version_number: int
    original_url: Optional[str] = None
    hash_value: Optional[str] = None

class RegulationVersionResponse(BaseModel):
    regulation_version_id: int
    regulation_id: int
    version_number: int
    created_at: datetime
    
    class Config:
        from_attributes = True
