from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.core.models.enums import ProductCategoryEnum

class ProductBase(BaseModel):
    product_name: str
    product_category: ProductCategoryEnum
    nicotin: Optional[float] = None
    tarr: Optional[float] = None
    menthol: bool = False
    incense: bool = False

class ProductCreate(ProductBase):
    manufactured_at: Optional[datetime] = None

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    nicotin: Optional[float] = None
    tarr: Optional[float] = None

class ProductResponse(ProductBase):
    product_id: int
    manufactured_at: Optional[datetime]
    
    class Config:
        from_attributes = True
