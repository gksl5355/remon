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


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

load_dotenv()

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
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
