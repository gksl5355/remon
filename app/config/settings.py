"""
module: settings.py
description: 환경 변수 및 기본 설정 관리
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
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


settings = Settings()
