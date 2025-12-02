from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, Numeric, func
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

    # Relationships
    country = relationship("Country", back_populates="products")
    impact_scores = relationship("ImpactScore", back_populates="products")
    reports = relationship("Report", back_populates="products")

# from sqlalchemy import Column, Integer, String, Enum, Boolean, Numeric, DateTime, ForeignKey
# from sqlalchemy.orm import relationship
# from datetime import datetime
# from .enums import ProductCategoryEnum
# from . import Base

# class Product(Base):
#     __tablename__ = "products"
    
#     product_id = Column(Integer, primary_key=True, autoincrement=True)
#     product_name = Column(String(100), nullable=False)
#     product_category = Column(Enum(ProductCategoryEnum), nullable=False)
#     manufactured_at = Column(DateTime, nullable=True)
#     nicotin = Column(Numeric(5, 2), nullable=True)
#     tarr = Column(Numeric(5, 2), nullable=True)
#     menthol = Column(Boolean, default=False)
#     incense = Column(Boolean, default=False)
#     battery = Column(String(50), nullable=True)
#     label_size = Column(String(50), nullable=True)
#     image = Column(String(255), nullable=True)
#     security_auth = Column(Boolean, default=False)
    
#     # Relationships
#     export_countries = relationship("ProductExportCountry", back_populates="product")
#     impact_scores = relationship("ImpactScore", back_populates="product")
#     reports = relationship("Report", back_populates="product")

# class ProductExportCountry(Base):
#     __tablename__ = "product_export_countries"
    
#     product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
#     country_code = Column(String(2), ForeignKey("countries.country_code"), primary_key=True)
#     note = Column(String(255), nullable=True)
    
#     # Relationships
#     product = relationship("Product", back_populates="export_countries")
#     country = relationship("Country", back_populates="product_exports")

