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
