"""
module: database.py
description: 비동기 SQLAlchemy 엔진 및 세션 주입(Dependency Injection) 설정
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - sqlalchemy.ext.asyncio
    - app.config.settings
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

logger = logging.getLogger(__name__)

# ✅ AsyncEngine 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   #데이터베이스 서버에 의해 연결이 예기치 않게 종료되었을 경우, 새로운 연결로 재시도하여 애플리케이션 오류를 방지
    echo=False,
)

# ✅ 세션 팩토리
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncSession:
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