"""
module: settings.py
description: 환경 변수 및 기본 설정 관리
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str
    # REDIS_URL: str
    # SECRET_KEY: str
    # CHROMA_DB_PATH: str
    # CHROMA_COLLECTION: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
