# """
# module: database.py
# description: SQLAlchemy 비동기 세션 관리
# """
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker
# from app.config.settings import settings

# engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
# AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# async def get_db():
#     async with AsyncSessionLocal() as session:
#         yield session

import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv


# app/core/database.py
# 실제 DB 연동을 위해 추가
# DB_URL = "postgresql+asyncpg://postgres:1234@localhost/remon_db"
# engine = create_async_engine(DB_URL)
# SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# def get_db_session():
#     return SessionLocal()




load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

# Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # 개발 시 SQL 로그 출력
    poolclass=NullPool,
    future=True
)

# Async Session Factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Dependency for FastAPI
async def get_db():
    """
    비동기 DB 세션을 생성하여 FastAPI 의존성으로 제공한다.

    Yields:
        AsyncSession: 트랜잭션 단위의 DB 세션 객체.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"DB session rollback due to error: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()
