from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ReportBase(BaseModel):
    created_reason: Optional[str] = None
    translation_id: int
    change_id: int
    product_id: int
    country_code: str

class ReportCreate(ReportBase):
    file_path: Optional[str] = None

class ReportResponse(ReportBase):
    report_id: int
    created_at: datetime
    file_path: Optional[str]
    
    class Config:
        from_attributes = True

class ReportItemCreate(BaseModel):
    regulation_version_id: int
    impact_score_id: int
    order_no: int

class ReportWithItemsResponse(ReportResponse):
    items: List["ReportItemResponse"]
    summaries: List["ReportSummaryResponse"]
