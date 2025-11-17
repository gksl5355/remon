"""Shared Pydantic models for vector metadata and mapping payloads.

전처리 파이프라인과 LangGraph 매핑 노드가 동일한 데이터 계약을 사용할 수 있도록
정의된 스키마 모음이다. 규제/제품 스냅샷, sparse payload 등
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, List, Any, Dict
from datetime import datetime


class SparseVectorPayload(BaseModel):
    """Sparse vector representation compatible with Qdrant."""

    indices: List[int]
    values: List[float]

    def sort(self) -> "SparseVectorPayload":
        """정렬된 새 인스턴스 반환."""
        pairs = sorted(zip(self.indices, self.values), key=lambda x: x[0])
        if not pairs:
            return self
        indices, values = zip(*pairs)
        return SparseVectorPayload(indices=list(indices), values=list(values))


class VectorMetadata(BaseModel):
    clause_id: str
    type: Literal["regulation", "product"]
    country: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    # 제품/규제 공통·확장 가능 슬롯들
    # TODO(remon-ai): 전처리 스키마 확정 시 최종 필드/단위 세트로 교체.
    nicotine: Optional[float] = None
    label_size: Optional[float] = None
    warning_area: Optional[float] = None
    battery_capacity: Optional[float] = None
    certified: Optional[bool] = None
    export_country: Optional[str] = None
    sparse_terms: Optional[Dict[str, float]] = None
    embedding_model: str = "bge-m3"

    sparse_terms: Optional[Dict[str, float]] = None
    embedding_model: str = "bge-m3"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProductSnapshot(BaseModel):
    """제품 RDB 스냅샷 → 매핑 노드 입력."""

    model_config = ConfigDict(from_attributes=True)

    id: int | str
    name: Optional[str] = None
    category: Optional[str] = None
    nicotine: Optional[float] = None
    tar: Optional[float] = None
    menthol: Optional[bool] = None
    flavor: Optional[bool] = None
    battery_capacity: Optional[float] = None
    label_size: Optional[float] = None
    warning_area: Optional[float] = None
    certified: Optional[bool] = None
    export_country: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class MappingResult(BaseModel):
    product_id: str
    regulation_id: str
    final_score: float
    hybrid_score: float | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    numeric_ratio: float | None = None
    condition_ratio: float | None = None
    matched_fields: List[str] | None = None  # ex) ["battery_capacity","label_size"]
    impact_level: int | None = None  # 1~3
    reason: str | None = None  # 간단 설명 문자열
    metadata: Any | None = None  # 규제/제품 메타 스냅샷
    timestamp: datetime = Field(default_factory=datetime.utcnow)
