from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def transaction_context(
    db: AsyncSession,
    nested: bool = False
) -> AsyncGenerator[AsyncSession, None]:
    """
    트랜잭션 컨텍스트 매니저
    
    Args:
        db: AsyncSession 인스턴스
        nested: True면 SAVEPOINT 사용 (중첩 트랜잭션)
    
    Yields:
        db: 트랜잭션이 활성화된 세션
    
    롤백 기준:
        - Exception 발생 시 자동 롤백
        - 정상 종료 시 자동 커밋
    
    Example:
        # 기본 트랜잭션
        async with transaction_context(db):
            await repo.create(db, **data)
            # 자동 커밋됨
        
        # 중첩 트랜잭션 (SAVEPOINT)
        async with transaction_context(db):
            await repo.create(db, **data1)
            
            try:
                async with transaction_context(db, nested=True):
                    await repo.create(db, **data2)
                    # 에러 발생 시 data2만 롤백
            except Exception:
                pass
            
            # data1은 커밋됨
    
    Note:
        - FastAPI의 get_db() dependency가 세션 생명주기를 관리하므로
          여기서는 close()를 호출하지 않음
        - Repository는 flush()만 사용하고, Service 계층에서 이 컨텍스트를 사용
    """
    if nested and db.in_transaction():
        # 중첩 트랜잭션 (SAVEPOINT) 사용
        async with db.begin_nested():
            try:
                yield db
            except Exception as e:
                logger.error(f"Nested transaction rolled back: {e}")
                raise
    else:
        # 일반 트랜잭션
        try:
            yield db
            await db.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            await db.rollback()
            logger.error(f"Transaction rolled back due to exception: {e}")
            raise
        # ❌ finally에서 close() 호출 안 함 (FastAPI dependency가 관리)


@asynccontextmanager
async def manual_transaction(
    db: AsyncSession
) -> AsyncGenerator[AsyncSession, None]:
    """
    수동 트랜잭션 관리 (Service 계층에서 명시적으로 commit/rollback)
    
    Args:
        db: AsyncSession
    
    Yields:
        db: 트랜잭션이 시작된 세션
    
    Example:
        async with manual_transaction(db) as session:
            await repo1.create(session, **data1)
            await repo2.create(session, **data2)
            
            if condition:
                await session.commit()
            else:
                await session.rollback()
    
    Note:
        - 커밋/롤백을 Service에서 명시적으로 제어해야 함
        - 자동 커밋/롤백 없음
    """
    try:
        yield db
    except Exception as e:
        logger.error(f"Manual transaction error: {e}")
        raise
    # 명시적으로 commit/rollback 하지 않으면 아무것도 안 함


async def safe_commit(db: AsyncSession) -> bool:
    """
    안전한 커밋
    
    Args:
        db: AsyncSession
    
    Returns:
        성공 여부
    
    롤백 기준:
        - 커밋 중 Exception 발생 시 자동 롤백
    """
    try:
        await db.commit()
        logger.debug("Commit successful")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Commit failed, rolled back: {e}")
        raise


async def safe_rollback(db: AsyncSession) -> None:
    """
    안전한 롤백
    
    Args:
        db: AsyncSession
    
    Note:
        - 롤백 중 예외가 발생해도 무시 (이미 에러 상태이므로)
    """
    try:
        await db.rollback()
        logger.debug("Rollback successful")
    except Exception as e:
        logger.warning(f"Rollback failed (ignored): {e}")
        pass


async def flush_and_refresh(db: AsyncSession, obj) -> None:
    """
    flush 후 객체 새로고침
    
    Args:
        db: AsyncSession
        obj: ORM 객체
    
    Note:
        - Repository에서 create/update 후 최신 상태 가져올 때 사용
    """
    try:
        await db.flush()
        await db.refresh(obj)
    except Exception as e:
        logger.error(f"Flush and refresh failed: {e}")
        raise


class TransactionError(Exception):
    """트랜잭션 관련 예외"""
    pass


async def check_transaction_state(db: AsyncSession) -> dict:
    """
    트랜잭션 상태 확인 (디버깅용)
    
    Args:
        db: AsyncSession
    
    Returns:
        트랜잭션 상태 정보
    """
    return {
        "in_transaction": db.in_transaction(),
        "is_active": db.is_active,
        "autocommit": db.autocommit,
        "bind": str(db.bind) if hasattr(db, 'bind') else None
    }



