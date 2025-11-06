"""
module: settings.py
description: 환경 변수 및 설정 관리.
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/ktg_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_REDIS: bool = False
    VECTOR_DB_PATH: str = "data/embeddings"
    OPENSEARCH_URL: str = "http://localhost:9200"
    LLM_API_KEY: str = ""

settings = Settings()
