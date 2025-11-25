from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel
from core.models.enums import ChangeTypeEnum

# --- Regulation Schemas ---

class RegulationBase(BaseModel):
    source_id: int
    country_code: str
    external_id: Optional[str] = None
    title: Optional[str] = None
    proclaimed_date: Optional[date] = None
    effective_date: Optional[date] = None
    language: Optional[str] = None
    status: Optional[str] = None

class RegulationCreate(RegulationBase):
    pass

class RegulationUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[date] = None

class RegulationResponse(RegulationBase):
    regulation_id: int
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 (v1이라면 orm_mode = True)


# --- Regulation Version Schemas ---

class RegulationVersionBase(BaseModel):
    regulation_id: int
    version_number: int
    original_uri: Optional[str] = None
    hash_value: Optional[str] = None

class RegulationVersionCreate(RegulationVersionBase):
    pass

class RegulationVersionResponse(RegulationVersionBase):
    regulation_version_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Regulation Change Keynote Schemas (대폭 수정됨) ---

class RegulationChangeKeynoteBase(BaseModel):
    # [변경] 기존의 product_id, title 등 개별 필드 대신 JSON 데이터 전체를 받음
    keynote_text: Optional[Dict[str, Any]] = None

class RegulationChangeKeynoteCreate(RegulationChangeKeynoteBase):
    keynote_text: Dict[str, Any]  # 생성 시 필수

class RegulationChangeKeynoteResponse(RegulationChangeKeynoteBase):
    keynote_id: int
    generated_at: datetime

    class Config:
        from_attributes = True


# --- Regulation Translation Schemas ---

class RegulationTranslationBase(BaseModel):
    regulation_version_id: int
    language_code: Optional[str] = None
    translated_text: Optional[str] = None
    glossary_term_id: Optional[str] = None # UUID string
    translation_status: Optional[str] = None

class RegulationTranslationCreate(RegulationTranslationBase):
    pass

class RegulationTranslationResponse(RegulationTranslationBase):
    translation_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Regulation Change History Schemas ---

class RegulationChangeHistoryBase(BaseModel):
    regulation_version_id: int
    change_type: Optional[ChangeTypeEnum] = None
    change_summary: Optional[str] = None

class RegulationChangeHistoryCreate(RegulationChangeHistoryBase):
    pass

class RegulationChangeHistoryResponse(RegulationChangeHistoryBase):
    change_id: int
    detected_at: datetime

    class Config:
        from_attributes = True