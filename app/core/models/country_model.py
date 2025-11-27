from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from . import Base

class Country(Base):
    __tablename__ = "countries"
    
    country_code = Column(String(2), primary_key=True)
    country_name = Column(String(100), nullable=False)
    
    # Relationships////////:100  varchar
    regulations = relationship("Regulation", back_populates="country")
    product_exports = relationship("ProductExportCountry", back_populates="country")
    reports = relationship("Report", back_populates="country")