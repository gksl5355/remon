"""
module: settings.py
description: 환경 변수 및 기본 설정 관리
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./remon.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "changeme"
    class Config:
        env_file = ".env"

settings = Settings()
