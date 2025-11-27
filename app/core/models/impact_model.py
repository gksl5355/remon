from sqlalchemy import Column, Integer, ForeignKey, Numeric, String, Text, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .enums import RiskLevelEnum
from . import Base

class ImpactScore(Base):
    __tablename__ = "impact_scores"
    
    impact_score_id = Column(Integer, primary_key=True, autoincrement=True)
    translation_id = Column(Integer, ForeignKey("regulation_translations.translation_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    # impact_score = Column(Numeric(5, 3), nullable=False)  # 0.000 ~ 1.000
    risk_level = Column(Enum(RiskLevelEnum), nullable=False)
    evaluation_detail = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    translation = relationship("RegulationTranslation", back_populates="impact_scores")
    product = relationship("Product", back_populates="impact_scores")
