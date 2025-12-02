"""
module: collect_api.py
description: 규제 문서 업로드 및 조회 API
author: 조영우
created: 2025-11-10
updated: 2025-12-02
dependencies:
    - fastapi
    - services.collect_service
    - core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.collect_service import CollectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collect", tags=["collect"])
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