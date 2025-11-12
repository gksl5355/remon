# vector_schema.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Any
from datetime import datetime


class VectorMetadata(BaseModel):
    clause_id: str
    type: Literal["regulation", "product"]
    country: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    # 제품/규제 공통·확장 가능 슬롯들
    nicotine: Optional[float] = None
    label_size: Optional[float] = None
    warning_area: Optional[float] = None
    battery_capacity: Optional[float] = None
    certified: Optional[bool] = None
    export_country: Optional[str] = None
    embedding_model: str = "bge-m3"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MappingResult(BaseModel):
    product_id: str
    regulation_id: str
    hybrid_score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    matched_fields: List[str] | None = None  # ex) ["battery_capacity","label_size"]
    impact_level: int | None = None  # 1~3
    reason: str | None = None  # 간단 설명 문자열
    metadata: Any | None = None  # 규제/제품 메타 스냅샷
    timestamp: datetime = Field(default_factory=datetime.utcnow)
