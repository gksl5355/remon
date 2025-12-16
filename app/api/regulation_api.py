"""
module: regulation_api.py
description: 규제-제품 매핑 조회 및 분석 API
author: 박선영
editor: 조영우
created: 2025-11-10
updated: 2025-11-12
dependencies:
    - fastapi
    - services.mapping_service
    - core.database
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.regulation_service import RegulationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Regulations"])
service = RegulationService()


@router.get("/regulations")
async def get_regulations(
    db: AsyncSession = Depends(get_db)
):
    """
    규제 문서 목록을 조회한다.
    
    Returns:
        dict: {"today_count": int, "regulations": list}
    """
    logger.info(f"GET /regulations - ")
    return await service.get_regulations(db)


@router.get("/regulations/{regulation_id}")
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
    reg = await service.get_regulation_detail(db, regulation_id)
    
    if not reg:
        logger.warning(f"Regulation not found: regulation_id={regulation_id}")
        raise HTTPException(status_code=404, detail="Regulation not found")
    
    return reg


@router.get("/regulations/country/{country}")
async def get_regulations_by_country(
    country: str,
    db: AsyncSession = Depends(get_db)
):
    """
    국가별 규제 목록 조회
    
    Args:
        country: 국가 코드 (US, ID, RU)
        
    Returns:
        dict: {"collectedTime": str, "files": list}
    """
    logger.info(f"GET /regulations/country/{country}")

    reg = await service.get_regulations_by_country(db, country)
    if not reg:
        logger.warning(f"Regulation not found: country={country}")
        raise HTTPException(status_code=404, detail="Regulation not found")
    return reg


@router.get("/regulations/country/{country}/file/{file_id}")
async def get_regulation_file_detail(
    country: str,
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 국가의 특정 파일 상세 정보 조회
    
    Args:
        country: 국가 코드
        file_id: 파일 ID
        
    Returns:
        dict: 파일 상세 정보
    """
    logger.info(f"GET /regulations/country/{country}/file/{file_id}")
    
    reg = await service.get_regulation_detail(db, file_id, country)
    if not reg:
        logger.warning(f"Regulation not found: country={country}, file_id={file_id}")
        raise HTTPException(status_code=404, detail="Regulation not found")
    return reg
