"""
module: base_repository.py
description: 공통 Repository 베이스 클래스 (commit 금지, 세션 주입 전용)
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - sqlalchemy.ext.asyncio
"""

from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

class BaseRepository:
    """Repository 계층의 공통 메서드 제공 (트랜잭션은 서비스 계층에서 관리)."""

    async def execute(self, db: AsyncSession, stmt):
        """
        쿼리를 실행하고 결과를 반환한다.

        Args:
            db (AsyncSession): SQLAlchemy 비동기 세션.
            stmt: 실행할 SQLAlchemy 문(statement).

        Returns:
            Result: SQLAlchemy 실행 결과 객체.
        """
        logger.debug(f"Executing SQL: {stmt}")
        result = await db.execute(stmt)
        return result