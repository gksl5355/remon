from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.models.enums import ProductCategoryEnum

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True) # SERIAL
    product_name = Column(String(50), nullable=False)
    product_category = Column(Enum(ProductCategoryEnum))
    manufactured_at = Column(DateTime, server_default=func.now())
    
    nicotine = Column(Numeric(5, 2))  # 소수점 처리
    tar = Column(Numeric(5, 2))
    menthol = Column(Boolean)
    flavor = Column(Boolean)          # 기존 incense -> flavor로 변경 추정
    label_size = Column(String(50))
    images_size = Column(String(50))
    package = Column(Text)
    certifying_agencies = Column(String(50))
    revenue = Column(Integer)
    
    # [변경] 1:N 관계 (제품 -> 국가)
    country_code = Column(String(2), ForeignKey("countries.country_code"))
    supply_partner = Column(String(50))
    regulation_trace = Column(JSONB)  # 규제 매핑/추적용 JSON

    # Relationships
    country = relationship("Country", back_populates="products")
    impact_scores = relationship("ImpactScore", back_populates="products")
    # reports = relationship("Report", back_populates="products")

