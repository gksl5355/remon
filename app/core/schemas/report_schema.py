from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

# --- Report Schemas ---

class ReportBase(BaseModel):
    translation_id: int
    country_code: str
    product_id: Optional[int] = None
    change_id: Optional[int] = None
    created_reason: Optional[str] = None
    file_path: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class ReportResponse(ReportBase):
    report_id: int
    created_at: datetime
    # [주의] 관계가 끊어졌으므로 summary 정보를 여기서 바로 nesting(중첩) 할 수 없습니다.
    # 만약 필요하다면 별도 로직으로 합쳐야 합니다.

    class Config:
        from_attributes = True  # Pydantic v2 (v1이라면 orm_mode = True)


# --- Report Item Schemas ---

class ReportItemBase(BaseModel):
    report_id: int
    regulation_version_id: Optional[int] = None
    impact_score_id: Optional[int] = None
    order_no: Optional[int] = None

class ReportItemCreate(ReportItemBase):
    pass

class ReportItemResponse(ReportItemBase):
    item_id: int

    class Config:
        from_attributes = True


# --- Report Summary Schemas (대폭 수정됨) ---

class ReportSummaryBase(BaseModel):
    # [변경] report_id, impact_score_id 제거 -> JSON 필드 하나로 통합
    summary_text: Optional[Dict[str, Any]] = None

class ReportSummaryCreate(ReportSummaryBase):
    summary_text: Dict[str, Any]  # 생성 시 필수

class ReportSummaryResponse(ReportSummaryBase):
    summary_id: int
    created_at: datetime

    class Config:
        from_attributes = True