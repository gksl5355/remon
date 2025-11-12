from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base

class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    
    glossary_term_id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_key = Column(String(100), nullable=False)
    language_code = Column(String(10), nullable=False)
    definition = Column(Text, nullable=False)
    synonyms = Column(String(500), nullable=True)
    mistranslations = Column(String(500), nullable=True)
    legal_terms = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    translations = relationship("RegulationTranslation", back_populates="glossary_term")
