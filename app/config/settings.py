"""
module: settings.py
description: 환경 변수 및 기본 설정 관리
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_COLLECTION: str
    # CHROMA_DB_PATH: str  # 사용 안함
    # CHROMA_COLLECTION: str  # 사용 안함

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # .env의 추가 필드 허용
    }
    QDRANT_API_KEY: str | None = None
    QDRANT_PREFER_GRPC: bool = False
    QDRANT_TIMEOUT: float = 10.0
    MAPPING_TOP_K: int = 10
    MAPPING_THRESHOLD: float = 0.45
    MAPPING_ALPHA: float = 0.7
    MAPPING_SEMANTIC_WEIGHT: float = 0.6
    MAPPING_NUMERIC_WEIGHT: float = 0.3
    MAPPING_CONDITION_WEIGHT: float = 0.1
    MAPPING_SINK_TYPE: str = "rdb"
    MAPPING_SINK_DSN: str | None = None


settings = Settings()
