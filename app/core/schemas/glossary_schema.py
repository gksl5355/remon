from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class GlossaryTermBase(BaseModel):
    """용어 사전 기본 스키마"""
    canonical_key: str = Field(..., min_length=1, max_length=100, description="표준 키")
    language_code: str = Field(..., min_length=2, max_length=10, description="언어 코드 (예: ko, en)")
    definition: str = Field(..., min_length=1, description="용어 정의")

class GlossaryTermCreate(GlossaryTermBase):
    """용어 사전 생성 스키마"""
    synonyms: Optional[str] = Field(None, max_length=500, description="동의어 (쉼표로 구분)")
    mistranslations: Optional[str] = Field(None, max_length=500, description="오역 사례")
    legal_terms: Optional[str] = Field(None, max_length=500, description="법률 용어")

class GlossaryTermUpdate(BaseModel):
    """용어 사전 수정 스키마"""
    canonical_key: Optional[str] = Field(None, min_length=1, max_length=100)
    language_code: Optional[str] = Field(None, min_length=2, max_length=10)
    definition: Optional[str] = None
    synonyms: Optional[str] = None
    mistranslations: Optional[str] = None
    legal_terms: Optional[str] = None

class GlossaryTermResponse(GlossaryTermBase):
    """용어 사전 응답 스키마"""
    glossary_term_id: int
    synonyms: Optional[str] = None
    mistranslations: Optional[str] = None
    legal_terms: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class GlossaryTermWithSynonyms(GlossaryTermResponse):
    """동의어 리스트를 포함한 용어"""
    synonyms_list: Optional[List[str]] = Field(None, description="파싱된 동의어 리스트")
    
    @classmethod
    def from_orm_with_parsing(cls, db_obj):
        """ORM 객체에서 생성하며 synonyms를 리스트로 파싱"""
        obj = cls.model_validate(db_obj)
        if obj.synonyms:
            obj.synonyms_list = [s.strip() for s in obj.synonyms.split(',')]
        return obj
