"""
module: admin_api.py
description: 관리자 기능 API (규제/리포트 관리)
author: 조영우
created: 2025-11-10
updated: 2025-11-10
dependencies:
    - fastapi
    - app.services.admin_service
    - app.core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])
service = AdminService()


@router.get("/regulations")
async def list_regulations(
    country: str | None = Query(None, description="국가 필터"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 규제 문서 목록을 조회한다.

    Returns:
        dict: 규제 문서 목록.
    """
    logger.info(f"GET /admin/regulations - country={country}, page={page}")
    return await service.get_regulations(db, country, page, page_size)


@router.delete("/regulations/{regulation_id}", status_code=204)
async def delete_regulation(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    규제 문서를 삭제한다.

    Args:
        regulation_id (int): 규제 문서 ID.

    Raises:
        HTTPException: 규제 문서를 찾을 수 없는 경우 404.
    """
    logger.info(f"DELETE /admin/regulations/{regulation_id}")
    success = await service.delete_regulation(db, regulation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Regulation not found")


@router.get("/reports")
async def list_reports(
    country: str | None = Query(None, description="국가 필터"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    관리자용 리포트 목록을 조회한다.

    Returns:
        dict: 리포트 목록.
    """
    logger.info(f"GET /admin/reports - country={country}, page={page}")
    return await service.get_admin_reports(db, country, page, page_size)
