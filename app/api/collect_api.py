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


@router.post("/crawl", status_code=201)
async def crawl_regulation(
    country: str = Query(..., description="국가명 (예: USA, Russia, Indonesia)"),
    keywords: list[str] = Query(..., description="검색 키워드 리스트"),
    category: str = Query("regulation", description="카테고리 (regulation 또는 news)"),
    db: AsyncSession = Depends(get_db)
):
    """
    DiscoveryAgent를 사용하여 규제 문서를 크롤링한다.

    Args:
        country (str): 국가명.
        keywords (list[str]): 검색 키워드 리스트.
        category (str): 카테고리 (regulation 또는 news).

    Returns:
        dict: 크롤링 결과.
    """
    logger.info(f"POST /collect/crawl - country={country}, keywords={keywords}, category={category}")
    
    try:
        result = await service.crawl_regulation(country, keywords, category, db)
        return result
    except Exception as e:
        logger.error(f"크롤링 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"크롤링 실패: {str(e)}")