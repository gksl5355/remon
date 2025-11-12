from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def transaction_context(db: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    트랜잭션 컨텍스트 매니저
    - 성공 시 commit
    - 실패 시 rollback
    """
    try:
        yield db
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
    finally:
        await db.close()

async def safe_commit(db: AsyncSession) -> bool:
    """안전한 커밋"""
    try:
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise e

async def safe_rollback(db: AsyncSession):
    """안전한 롤백"""
    try:
        await db.rollback()
    except Exception:
        pass
