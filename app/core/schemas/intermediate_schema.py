from typing import Optional, Dict, Any
from pydantic import BaseModel

class IntermediateOutputBase(BaseModel):
    regulation_id: int
    intermediate_data: Optional[Dict[str, Any]] = None

class IntermediateOutputCreate(IntermediateOutputBase):
    # 생성 시 필요한 데이터 (Base와 동일하면 pass)
    pass

class IntermediateOutputResponse(IntermediateOutputBase):
    intermediate_id: int

    class Config:
        from_attributes = True