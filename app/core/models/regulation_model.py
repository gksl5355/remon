from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Enum, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID  # UUID 사용 시 필요
from app.core.database import Base
from app.core.models.enums import ChangeTypeEnum, TranslationStatusEnum  # 프로젝트 구조에 맞게 import 경로 확인 필요

class Regulation(Base):
    __tablename__ = "regulations"

    regulation_id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.source_id"), nullable=False)
    country_code = Column(String(2), ForeignKey("countries.country_code"), nullable=False)
    external_id = Column(String(200))
    title = Column(String(200))
    proclaimed_date = Column(Date)
    effective_date = Column(Date)
    language = Column(String(10))
    status = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    data_source = relationship("DataSource", back_populates="regulations")
    country = relationship("Country", back_populates="regulations")
    version = relationship("RegulationVersion", back_populates="regulations", cascade="all, delete-orphan")


class RegulationVersion(Base):
    __tablename__ = "regulation_versions"

    regulation_version_id = Column(Integer, primary_key=True, index=True)
    regulation_id = Column(Integer, ForeignKey("regulations.regulation_id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    original_uri = Column(String(500))
    hash_value = Column(String(128))
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    regulations = relationship("Regulation", back_populates="version")
    translations = relationship("RegulationTranslation", back_populates="version", cascade="all, delete-orphan")
    changes = relationship("RegulationChangeHistory", back_populates="version", cascade="all, delete-orphan")
    # [삭제됨] Keynotes와의 관계 제거


class RegulationChangeKeynote(Base):
    __tablename__ = "regulation_change_keynotes"

    keynote_id = Column(Integer, primary_key=True, index=True)
    
    # [변경] 기존 FK 컬럼들 삭제 후 JSONB 컬럼 하나로 통합
    keynote_text = Column(JSONB)
    
    generated_at = Column(DateTime, server_default=func.now())

    # [변경] FK 제거로 인해 모든 Relationship 삭제됨

class RegulationTranslation(Base):
    __tablename__ = "regulation_translations"

    translation_id = Column(Integer, primary_key=True, index=True) # SERIAL
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    language_code = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=True)
    glossary_term_id = Column(Integer, ForeignKey("glossary_terms.glossary_term_id"))
    # glossary_term_id = Column(UUID(as_uuid=True), ForeignKey("glossary_terms.glossary_term_id"), nullable=True)
    
    # [변경] 상태 Enum 및 기본값 적용
    translation_status = Column(Enum(TranslationStatusEnum), default=TranslationStatusEnum.queued, nullable=False)
    
    # [신규] S3 Key 및 타임스탬프
    s3_key = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)



class RegulationChangeHistory(Base):
    __tablename__ = "regulation_change_history"

    change_id = Column(Integer, primary_key=True, index=True)
    regulation_version_id = Column(Integer, ForeignKey("regulation_versions.regulation_version_id"), nullable=False)
    change_type = Column(Enum(ChangeTypeEnum), nullable=True)
    change_summary = Column(Text)
    detected_at = Column(DateTime, server_default=func.now())

    # Relationships
    version = relationship("RegulationVersion", back_populates="translations")
    # reports = relationship("Report", back_populates="changes")