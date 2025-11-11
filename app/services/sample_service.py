"""
module: sample_service.py
description: 트랜잭션 관리 구조 검증용 샘플 서비스
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - app.core.repositories.base_repository
"""

# app/services/sample_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.base_repository import BaseRepository
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class SampleService:
    """트랜잭션 관리 테스트용 샘플 서비스 클래스."""

    def __init__(self):
        self.repo = BaseRepository()

    async def test_transaction(self, db: AsyncSession) -> dict:
        """
        PostgreSQL 트랜잭션 커밋 테스트용.
        INSERT 후 커밋되면 test_log 테이블에 데이터가 남는다.
        """
        logger.info("Starting PostgreSQL transaction test.")
        async with db.begin():  # ✅ 트랜잭션 경계
            stmt = text("INSERT INTO test_log (message) VALUES (:msg)")
            await self.repo.execute(db, stmt.params(msg="Transaction test OK"))
            logger.info("Inserted test_log row successfully.")
        logger.info("Transaction committed successfully.")
        return {"ok": True, "message": "Inserted into test_log."}
