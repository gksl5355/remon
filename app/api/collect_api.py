"""
module: collect_api.py
description: 규제 문서 업로드 및 조회 API
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - fastapi
    - app.services.collect_service
    - app.core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.collect_service import CollectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/regulations", tags=["Regulations"])
service = CollectService()


@router.post("/upload", status_code=201)
async def upload_regulation(
    file: UploadFile = File(...),
    country: str = Query(..., description="국가 코드 (예: KR, US)"),
    db: AsyncSession = Depends(get_db)
):
    """
    규제 PDF 파일을 업로드한다.

    Args:
        file (UploadFile): PDF 파일.
        country (str): 국가 코드.

    Returns:
        dict: 업로드된 규제 ID 및 상태.
    """
    logger.info(f"POST /regulations/upload - filename={file.filename}, country={country}")
    return await service.process_upload(file, country, db)


@router.post("/url", status_code=201)
async def collect_from_url(
    url: str,
    country: str,
    db: AsyncSession = Depends(get_db)
):
    """
    URL로 규제 문서를 수집한다.

    Args:
        url (str): 규제 문서 URL.
        country (str): 국가 코드.

    Returns:
        dict: 수집된 규제 ID 및 상태.
    """
    logger.info(f"POST /regulations/url - url={url}, country={country}")
    return await service.process_url(url, country, db)


@router.get("/")
async def list_regulations(
    country: str | None = Query(None, description="국가 필터"),
    status: str | None = Query(None, description="상태 필터 (active/repealed)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    규제 문서 목록을 조회한다.

    Returns:
        dict: 규제 문서 목록 및 페이지네이션 정보.
    """
    logger.info(f"GET /regulations - country={country}, status={status}, page={page}")
    return await service.get_regulations(country, status, page, page_size, db)


@router.get("/{regulation_id}")
async def get_regulation(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    규제 문서 상세 정보를 조회한다.

    Args:
        regulation_id (int): 규제 문서 ID.

    Returns:
        dict: 규제 문서 상세 정보.

    Raises:
        HTTPException: 규제 문서를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /regulations/{regulation_id}")
    regulation = await service.get_regulation_detail(regulation_id, db)
    
    if not regulation:
        logger.warning(f"Regulation not found: regulation_id={regulation_id}")
        raise HTTPException(status_code=404, detail="Regulation not found")
    
    return regulation
