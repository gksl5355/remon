from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal
from app.core.models.enums import ProductCategoryEnum

class ProductBase(BaseModel):
    product_name: str
    product_category: Optional[ProductCategoryEnum] = None
    manufactured_at: Optional[datetime] = None
    
    nicotine: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    tar: Optional[Decimal] = Field(None, max_digits=5, decimal_places=2)
    menthol: Optional[bool] = None
    flavor: Optional[bool] = None
    label_size: Optional[str] = None
    images_size: Optional[str] = None
    package: Optional[str] = None
    certifying_agencies: Optional[str] = None
    revenue: Optional[int] = None
    country_code: Optional[str] = None
    supply_partner: Optional[str] = None
    effective: Optional[dict] = None

class ProductCreate(ProductBase):
    product_name: str # 필수
    # 필요한 경우 필수 필드 추가

class ProductResponse(ProductBase):
    product_id: int

    class Config:
        from_attributes = True

