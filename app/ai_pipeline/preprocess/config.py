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

import os
from typing import Optional
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

    # ==================== Chunking ====================
    MAX_CHUNK_SIZE: int = 1024
    """청크 최대 토큰 크기. 기본값: 1024"""

    # ==================== Chunking ====================
    MAX_CHUNK_SIZE: int = 1024
    """청크 최대 토큰 크기. 기본값: 1024"""
    
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
    
    # ==================== Vision Pipeline ====================
    VISION_MODEL_COMPLEX: str = os.getenv("VISION_MODEL_COMPLEX", "gpt-4o")
    """복잡한 표 처리용 Vision 모델. 기본값: gpt-4o"""
    
    VISION_MODEL_SIMPLE: str = os.getenv("VISION_MODEL_SIMPLE", "gpt-4o-mini")
    """단순 텍스트 처리용 Vision 모델. 기본값: gpt-4o-mini"""
    
    VISION_DPI: int = int(os.getenv("VISION_DPI", "300"))
    """PDF 이미지 렌더링 DPI. 기본값: 300"""
    
    COMPLEXITY_THRESHOLD: float = float(os.getenv("COMPLEXITY_THRESHOLD", "0.3"))
    """표 복잡도 임계값 (0-1). 이상이면 GPT-4o 사용. 기본값: 0.3"""
    
    VISION_MAX_TOKENS: int = int(os.getenv("VISION_MAX_TOKENS", "16384"))
    """Vision LLM 최대 출력 토큰. 기본값: 16384 (Prompt Caching 효율화)"""
    
    VISION_TEMPERATURE: float = float(os.getenv("VISION_TEMPERATURE", "0.1"))
    """Vision LLM 온도 (구조 추출용 낮게). 기본값: 0.1"""
    
    ENABLE_GRAPH_EXTRACTION: bool = os.getenv("ENABLE_GRAPH_EXTRACTION", "true").lower() == "true"
    """지식 그래프 추출 활성화. 기본값: True"""
    
    DOCUMENT_ANALYSIS_PAGES: int = int(os.getenv("DOCUMENT_ANALYSIS_PAGES", "3"))
    """문서 규칙 파악용 초기 분석 페이지 수. 기본값: 3"""
    
    # ==================== 병렬 처리 설정 ====================
    VISION_MAX_CONCURRENCY: int = int(os.getenv("VISION_MAX_CONCURRENCY", "30"))
    """페이지별 Vision LLM 호출 최대 동시 실행 수. 기본값: 30"""
    
    VISION_TOKEN_BUDGET: Optional[int] = (
        int(os.getenv("VISION_TOKEN_BUDGET")) if os.getenv("VISION_TOKEN_BUDGET") else None
    )
    """문서 단위 토큰 예산 (None이면 제한 없음). 기본값: None"""
    
    # ==================== 배치 처리 설정 ====================
    VISION_BATCH_SIZE_SIMPLE: int = int(os.getenv("VISION_BATCH_SIZE_SIMPLE", "5"))
    """gpt-4o-mini용 배치 크기. 기본값: 5"""
    
    VISION_BATCH_SIZE_COMPLEX: int = int(os.getenv("VISION_BATCH_SIZE_COMPLEX", "2"))
    """gpt-4o용 배치 크기. 기본값: 2"""
    
    VISION_REQUEST_TIMEOUT: int = int(os.getenv("VISION_REQUEST_TIMEOUT", "120"))
    """Vision API 요청 타임아웃 (초). 기본값: 120"""
    
    VISION_RETRY_MAX_ATTEMPTS: int = int(os.getenv("VISION_RETRY_MAX_ATTEMPTS", "2"))
    """Vision API 실패 시 최대 재시도 횟수. 기본값: 2"""
    
    VISION_RETRY_BACKOFF_SECONDS: float = float(os.getenv("VISION_RETRY_BACKOFF_SECONDS", "1.0"))
    """재시도 간 대기 시간 (초). 기본값: 1.0"""
    
    # ==================== LangSmith (추적) ====================
    ENABLE_LANGSMITH: bool = (
        os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    )
    """LangSmith 추적 활성화 여부"""

    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    """LangSmith API 키 (.env에서 로드)"""

    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "remon-vision-pipeline")
    """LangSmith 프로젝트명 (.env에서 로드). 기본값: remon-vision-pipeline"""

    @classmethod
    def setup_langsmith(cls) -> None:
        """LangSmith 환경변수 설정."""
        if cls.ENABLE_LANGSMITH and cls.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = cls.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = cls.LANGCHAIN_PROJECT
            logger.info(f"✅ LangSmith 활성화: {cls.LANGCHAIN_PROJECT}")
        else:
            logger.info("⚠️ LangSmith 비활성화")

    @classmethod
    def wrap_openai_client(cls, client):
        """OpenAI 클라이언트를 LangSmith wrapper로 감싸기."""
        if cls.ENABLE_LANGSMITH and cls.LANGCHAIN_API_KEY:
            try:
                from langsmith.wrappers import wrap_openai

                wrapped_client = wrap_openai(client)
                logger.debug("OpenAI 클라이언트에 LangSmith wrapper 적용")
                return wrapped_client
            except ImportError:
                logger.warning("langsmith 패키지가 설치되지 않음, wrapper 적용 건너뜀")
                return client
        return client

    # ==================== Redis (비동기 선택사항) ====================
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    """Redis 연결 URL (.env에서 로드). 기본값: None (비동기 비활성화)"""

    ENABLE_REDIS_ASYNC: bool = (
        os.getenv("ENABLE_REDIS_ASYNC", "false").lower() == "true"
    )
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
        if cls.MAX_CHUNK_SIZE < 100:
            raise ValueError(f"MAX_CHUNK_SIZE must be >= 100, got {cls.MAX_CHUNK_SIZE}")

        if cls.EMBEDDING_DIMENSION != 1024:
            raise ValueError(
                f"BGE-M3 requires EMBEDDING_DIMENSION=1024, got {cls.EMBEDDING_DIMENSION}"
            )

        if not cls.QDRANT_PATH or not cls.QDRANT_COLLECTION:
            raise ValueError("QDRANT_PATH and QDRANT_COLLECTION must be set")

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
    def get_vision_config(cls) -> dict:
        """Vision Pipeline 설정 딕셔너리 반환."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return {
            "api_key": cls.OPENAI_API_KEY,
            "model_complex": cls.VISION_MODEL_COMPLEX,
            "model_simple": cls.VISION_MODEL_SIMPLE,
            "dpi": cls.VISION_DPI,
            "complexity_threshold": cls.COMPLEXITY_THRESHOLD,
            "max_tokens": cls.VISION_MAX_TOKENS,
            "temperature": cls.VISION_TEMPERATURE,
            "enable_graph": cls.ENABLE_GRAPH_EXTRACTION,
            "analysis_pages": cls.DOCUMENT_ANALYSIS_PAGES,
            "max_concurrency": cls.VISION_MAX_CONCURRENCY,
            "token_budget": cls.VISION_TOKEN_BUDGET,
            "request_timeout": cls.VISION_REQUEST_TIMEOUT,
            "retry_max_attempts": cls.VISION_RETRY_MAX_ATTEMPTS,
            "retry_backoff_seconds": cls.VISION_RETRY_BACKOFF_SECONDS,
            "batch_size_simple": cls.VISION_BATCH_SIZE_SIMPLE,
            "batch_size_complex": cls.VISION_BATCH_SIZE_COMPLEX,
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
