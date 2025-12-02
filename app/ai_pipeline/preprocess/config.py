"""
module: config.py
description: Preprocess 모듈 설정 관리 (기존 REMON 설정과 호환, 상대경로 사용)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12 (수정: 절대경로→상대경로, 공동작업 지원)
dependencies:
    - app.config.settings (기존 REMON 설정)
    - .env (프로젝트 루트의 환경 변수)

주의: 프로젝트 루트(/home/minje/remon)에서 실행해야 .env가 제대로 로드됩니다.
절대경로를 사용하지 않으므로 git clone 후 모든 개발자가 동일하게 작동합니다.
"""

from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

# ==================== 기존 REMON 설정 활용 ====================
# app/config/settings.py에서 .env를 이미 로드했으므로 그것을 재사용
# .env가 없으면 기본값 사용 (상대경로만 사용)
# Qdrant 설정 (환경변수에서 직접 로드)
try:
    from app.config.settings import settings as remon_settings
    logger.info(f"✅ REMON 기존 설정 로드 시도")
except (ImportError, AttributeError, ValueError) as e:
    logger.warning(f"⚠️ REMON 설정 로드 실패, 환경변수에서 직접 로드: {e}")


class PreprocessConfig:
    """
    Preprocess 모듈 설정 클래스 (딕셔너리 기반).
    
    환경 변수 또는 기본값에서 설정값을 로드합니다.
    """

    # ==================== PDF Processing ====================
    MAX_CHUNK_SIZE: int = 1500
    """청크 최대 크기 (문자 단위). 기본값: 1500"""
    
    TABLE_BBOX_THRESHOLD: float = 0.5
    """테이블 겹침 감지 임계값 (0-1). 기본값: 0.5"""
    
    PRESERVE_TABLE_INTEGRITY: bool = True
    """테이블 분할 금지 여부. 기본값: True"""
    
    # ==================== Embedding ====================
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    """임베딩 모델명. 기본값: BAAI/bge-m3"""
    
    EMBEDDING_DIMENSION: int = 1024
    """BGE-M3 벡터 차원. 기본값: 1024 (변경 금지)"""
    
    MAX_EMBEDDING_LENGTH: int = 8192
    """임베딩 최대 텍스트 길이. 기본값: 8192"""
    
    USE_FP16: bool = True
    """FP16 정밀도 사용 (메모리 절약). 기본값: True"""
    
    EMBEDDING_BATCH_SIZE: int = 32
    """배치 임베딩 크기. 기본값: 32"""
    
    # ==================== Chunking Strategy ====================
    SEMANTIC_CHUNK_STRATEGY: str = "hierarchy"
    """청킹 전략. 옵션: hierarchy, fixed. 기본값: hierarchy"""
    
    FORCE_SECTION_BREAK: bool = True
    """섹션 경계에서 강제 분리. 기본값: True"""
    
    # ==================== Hybrid Search ====================
    HYBRID_ALPHA: float = 0.5
    """하이브리드 검색 가중치. 0.5 = 50% 의미검색 + 50% BM25. 범위: 0-1"""
    
    TABLE_BOOST: float = 1.3
    """테이블 포함 청크 점수 부스트. 기본값: 1.3"""
    
    CATEGORY_BOOST: float = 1.3
    """카테고리 매칭 점수 부스트. 기본값: 1.3"""
    
    SEARCH_TOP_K: int = 5
    """검색 결과 상위 K개. 기본값: 5"""
    
    # ==================== Proposition Extraction ====================
    PROPOSITION_BATCH_SIZE: int = 3
    """명제 추출 병렬 워커 수. 기본값: 3"""
    
    PROPOSITION_MODEL: str = "gpt-4o-mini"
    """명제 추출용 LLM 모델. 기본값: gpt-4o-mini"""
    
    MAX_PROPOSITIONS_PER_CHUNK: int = 5
    """청크당 최대 명제 수. 기본값: 5"""
    
    PROPOSITION_TEMPERATURE: float = 0.3
    """명제 추출 LLM 온도 (일관성). 기본값: 0.3"""
    
    PROPOSITION_MAX_TOKENS: int = 500
    """명제 추출 LLM 최대 토큰. 기본값: 500"""
    
    # ==================== Metadata ====================
    EXTRACT_LEGAL_HIERARCHY: bool = True
    """법률 계층 구조 추출 여부. 기본값: True"""
    
    DETECT_CATEGORY: bool = True
    """규제 카테고리 감지 여부. 기본값: True"""
    
    # ==================== VectorDB (Qdrant) ====================
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    """Qdrant 서버 호스트. 기본값: localhost"""
    
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    """Qdrant 서버 포트. 기본값: 6333"""
    
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", "./data/qdrant")
    """Qdrant 로컬 저장소 경로. 기본값: ./data/qdrant"""
    
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "remon_regulations")
    """Qdrant 컬렉션명. 기본값: remon_regulations"""
    
    # ==================== 로그 & 데이터 디렉토리 (상대경로) ====================
    LOG_DIR: str = "./logs/preprocess"
    """로그 디렉토리 (상대경로, 프로젝트 루트 기준). 예: ./logs/preprocess"""
    
    DATA_DIR: str = "./data"
    """데이터 디렉토리 (상대경로, 프로젝트 루트 기준). 예: ./data"""
    
    EMBEDDINGS_DIR: str = "./data/embeddings"
    """임베딩 데이터 디렉토리 (상대경로, 프로젝트 루트 기준). 예: ./data/embeddings"""
    
    # ==================== OpenAI (명제 & 답변) ====================
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    """OpenAI API 키 (.env에서 로드)"""
    
    OPENAI_MODEL_PROPOSITION: str = os.getenv("OPENAI_MODEL_PROPOSITION", "gpt-4o-mini")
    """명제 추출용 모델. 기본값: gpt-4o-mini"""
    
    OPENAI_MODEL_ANSWER: str = os.getenv("OPENAI_MODEL_ANSWER", "gpt-4o-mini")
    """답변 생성용 모델. 기본값: gpt-4o-mini"""
    
    OPENAI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", "30"))
    """OpenAI 요청 타임아웃 (초). 기본값: 30"""
    
    # ==================== LangSmith (추적) ====================
    ENABLE_LANGSMITH: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    """LangSmith 추적 활성화 여부"""
    
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    """LangSmith API 키 (.env에서 로드)"""
    
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "remon-advanced-rag")
    """LangSmith 프로젝트명 (.env에서 로드). 기본값: remon-advanced-rag"""
    
    # ==================== Redis (비동기 선택사항) ====================
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    """Redis 연결 URL (.env에서 로드). 기본값: None (비동기 비활성화)"""
    
    ENABLE_REDIS_ASYNC: bool = os.getenv("ENABLE_REDIS_ASYNC", "false").lower() == "true"
    """Redis 기반 비동기 처리 활성화 (.env에서 로드). 기본값: False"""
    
    REDIS_TASK_QUEUE: str = "remon:proposition:tasks"
    """Redis 작업 큐 키. 기본값: remon:proposition:tasks"""
    
    # ==================== Logging ====================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    """로그 레벨. 옵션: DEBUG, INFO, WARNING, ERROR, CRITICAL. 기본값: INFO"""
    
    # ==================== Development ====================
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    """디버그 모드 (verbose 출력). 기본값: False"""
    
    SKIP_EMBEDDING_CACHE: bool = False
    """임베딩 캐시 스킵 (항상 재생성). 기본값: False"""
    
    @classmethod
    def validate(cls) -> None:
        """설정값 유효성 검증."""
        # Alpha 범위 검증
        if not (0 <= cls.HYBRID_ALPHA <= 1):
            raise ValueError(f"HYBRID_ALPHA must be between 0 and 1, got {cls.HYBRID_ALPHA}")
        
        # 청크 크기 검증
        if cls.MAX_CHUNK_SIZE < 100:
            raise ValueError(f"MAX_CHUNK_SIZE must be >= 100, got {cls.MAX_CHUNK_SIZE}")
        
        # 임베딩 차원 검증 (BGE-M3 고정)
        if cls.EMBEDDING_DIMENSION != 1024:
            raise ValueError(f"BGE-M3 requires EMBEDDING_DIMENSION=1024, got {cls.EMBEDDING_DIMENSION}")
        
        # 로그 레벨 검증
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if cls.LOG_LEVEL not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got {cls.LOG_LEVEL}")
        
        # Qdrant 경로 검증
        if not cls.QDRANT_PATH:
            raise ValueError("QDRANT_PATH is not set. Check .env file")
        
        if not cls.QDRANT_COLLECTION:
            raise ValueError("QDRANT_COLLECTION is not set. Check .env file")
    
    @classmethod
    def get_embedding_config(cls) -> dict:
        """임베딩 설정 딕셔너리 반환."""
        return {
            "model": cls.EMBEDDING_MODEL,
            "dimension": cls.EMBEDDING_DIMENSION,
            "max_length": cls.MAX_EMBEDDING_LENGTH,
            "use_fp16": cls.USE_FP16,
            "batch_size": cls.EMBEDDING_BATCH_SIZE,
        }
    
    @classmethod
    def get_chunking_config(cls) -> dict:
        """청킹 설정 딕셔너리 반환."""
        return {
            "max_size": cls.MAX_CHUNK_SIZE,
            "strategy": cls.SEMANTIC_CHUNK_STRATEGY,
            "preserve_table": cls.PRESERVE_TABLE_INTEGRITY,
            "force_section_break": cls.FORCE_SECTION_BREAK,
        }
    
    @classmethod
    def get_search_config(cls) -> dict:
        """검색 설정 딕셔너리 반환."""
        return {
            "alpha": cls.HYBRID_ALPHA,
            "table_boost": cls.TABLE_BOOST,
            "category_boost": cls.CATEGORY_BOOST,
            "top_k": cls.SEARCH_TOP_K,
        }
    
    @classmethod
    def get_openai_config(cls) -> dict:
        """OpenAI 설정 딕셔너리 반환."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return {
            "api_key": cls.OPENAI_API_KEY,
            "model_proposition": cls.OPENAI_MODEL_PROPOSITION,
            "model_answer": cls.OPENAI_MODEL_ANSWER,
            "timeout": cls.OPENAI_TIMEOUT,
        }
    
    @classmethod
    def get_qdrant_config(cls) -> dict:
        """Qdrant 설정 딕셔너리 반환."""
        return {
            "host": cls.QDRANT_HOST,
            "port": cls.QDRANT_PORT,
            "path": cls.QDRANT_PATH,
            "collection": cls.QDRANT_COLLECTION,
        }

        
    
