from sqlalchemy import Column, Integer, String, Enum, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .enums import ProductCategoryEnum
from . import Base

class Product(Base):
    __tablename__ = "products"
    
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(100), nullable=False)
    product_category = Column(Enum(ProductCategoryEnum), nullable=False)
    manufactured_at = Column(DateTime, nullable=True)
    nicotin = Column(Numeric(5, 2), nullable=True)
    tarr = Column(Numeric(5, 2), nullable=True)
    menthol = Column(Boolean, default=False)
    incense = Column(Boolean, default=False)
    battery = Column(String(50), nullable=True)
    label_size = Column(String(50), nullable=True)
    image = Column(String(255), nullable=True)
    security_auth = Column(Boolean, default=False)
    
    # Relationships
    export_countries = relationship("ProductExportCountry", back_populates="product")
    impact_scores = relationship("ImpactScore", back_populates="product")
    keynotes = relationship("RegulationChangeKeynote", back_populates="product")

class ProductExportCountry(Base):
    __tablename__ = "product_export_countries"
    
    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    country_code = Column(String(2), ForeignKey("countries.country_code"), primary_key=True)
    note = Column(String(255), nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="export_countries")
    country = relationship("Country", back_populates="product_exports")
