"""
module: sample_api.py
description: 트랜잭션 동작 검증용 테스트 API
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - fastapi
    - app.services.sample_service
    - app.core.database
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.sample_service import SampleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sample", tags=["Sample"])
service = SampleService()

@router.post("/test")
async def test_transaction_api(db: AsyncSession = Depends(get_db)):
    """
    DB 트랜잭션 구조 테스트용 API.

    Returns:
        dict: {"ok": True} 응답 시 트랜잭션 세팅 성공.
    """
    logger.info("Received /sample/test request.")
    return await service.test_transaction(db)