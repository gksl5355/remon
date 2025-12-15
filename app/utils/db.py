import os
import logging
from typing import Any, Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ==================================================
# DATABASE ENGINE / SESSION
# ==================================================

DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql+asyncpg://...

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,   # 끊긴 커넥션 자동 감지
    pool_recycle=1800,    # 30분 이상 idle 시 재생성
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # ⭐ commit 후에도 데이터 유지
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        try:
            await session.close()
        except Exception as e:
            logger.warning("DB session already closed: %s", e)


# ==================================================
# QUERY FUNCTIONS
# ==================================================

async def fetch_regul_data_by_title(
    db: AsyncSession,
    title: str,
) -> Optional[Any]:

    logger.info("fetch_regul_data_by_title")
    logger.info("title = %s", title)

    result = await db.execute(
        text(
            """
            SELECT regul_data
            FROM regulations
            WHERE title = :title
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"title": title},
    )

    row = result.mappings().first()

    if not row:
        logger.warning("❌ regul_data not found | title=%s", title)
        return None

    regul_data = row["regul_data"]

    logger.info(
        "✅ regul_data loaded | type=%s",
        type(regul_data).__name__,
    )

    if isinstance(regul_data, (list, dict)):
        logger.info("regul_data size=%d", len(regul_data))

    return regul_data
