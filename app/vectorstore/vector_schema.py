from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class VectorMetadata(BaseModel):
    clause_id: str
    type: Literal["regulation", "product"]
    country: Optional[str] = None
    category: Optional[str] = None
    nicotine: Optional[float] = None
    label_size: Optional[float] = None
    warning_area: Optional[float] = None
    battery_capacity: Optional[float] = None
    certified: Optional[bool] = None
    export_country: Optional[str] = None
    embedding_model: str = "bge-m3"
    created_at: datetime = datetime.utcnow()

    class Config:
        orm_mode = True
