from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .enums import ChangeTypeEnum
from . import Base

class Regulation(Base):
    __tablename__ = "regulations"
    
    regulation_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=False)
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)
    external_id = Column(String(100), nullable=True)
    title = Column(Text, nullable=True)
    proclaimed_date = Column(DateTime, nullable=True)
    effective_date = Column(DateTime, nullable=True)
    language = Column(String(10), nullable=True)
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    data_source = relationship("DataSource", back_populates="regulations")
    country = relationship("Country", back_populates="regulations")
    versions = relationship("RegulationVersion", back_populates="regulation", cascade="all, delete-orphan")

class RegulationVersion(Base):
    __tablename__ = "regulation_versions"
    
    regulation_version_id = Column(Integer, primary_key=True, autoincrement=True)
    regulation_id = Column(Integer, ForeignKey("regulations.regulation_id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    original_url = Column(String(500), nullable=True)
    hash_value = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    regulation = relationship("Regulation", back_populates="versions")
    translations = relationship("RegulationTranslation", back_populates="version", cascade="all, delete-orphan")
    change_histories = relationship("RegulationChangeHistory", back_populates="version")
    report_items = relationship("ReportItem", back_populates="regulation_version")
    keynotes = relationship("RegulationChangeKeynote", back_populates="regulation_version")

class RegulationTranslation(Base):
    __tablename__ = "regulation_translations"
    
    translation_id = Column(Integer, primary_key=True, autoincrement=True)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    language_code = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=False)
    glossary_term_id = Column(Integer, ForeignKey("glossary_terms.glossary_term_id"), nullable=True)
    translation_status = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    version = relationship("RegulationVersion", back_populates="translations")
    glossary_term = relationship("GlossaryTerm", back_populates="translations")
    impact_scores = relationship("ImpactScore", back_populates="translation")
    keynotes = relationship("RegulationChangeKeynote", back_populates="translation")

class RegulationChangeHistory(Base):
    __tablename__ = "regulation_change_history"
    
    change_id = Column(Integer, primary_key=True, autoincrement=True)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    change_type = Column(Enum(ChangeTypeEnum), nullable=False)
    change_summary = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    version = relationship("RegulationVersion", back_populates="change_histories")

class RegulationChangeKeynote(Base):
    __tablename__ = "regulation_change_keynotes"
    
    keynote_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    impact_score_id = Column(Integer, ForeignKey("impact_scores.impact_score_id"), nullable=False)
    translation_id = Column(Integer, ForeignKey("regulation_translations.translation_id"), nullable=False)
    title = Column(Text, nullable=True)
    regulation_type = Column(String(100), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="keynotes")
    regulation_version = relationship("RegulationVersion", back_populates="keynotes")
    impact_score = relationship("ImpactScore", back_populates="keynotes")
    translation = relationship("RegulationTranslation", back_populates="keynotes")
