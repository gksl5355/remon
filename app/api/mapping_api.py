"""
module: mapping_api.py
description: 규제-제품 매핑 조회 및 분석 API
author: 조영우
created: 2025-11-10
updated: 2025-11-10
dependencies:
    - fastapi
    - services.mapping_service
    - core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.mapping_service import MappingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mapping", tags=["Mapping"])
service = MappingService()


@router.get("/{regulation_id}")
async def get_mapping_results(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 규제에 대한 제품 매핑 결과를 조회한다.

    Args:
        regulation_id (int): 규제 문서 ID.

    Returns:
        dict: 매핑 결과.

    Raises:
        HTTPException: 매핑 결과를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /mapping/{regulation_id}")
    result = await service.get_mapping_results(db, regulation_id)
    
    if not result:
        logger.warning(f"Mapping results not found for regulation_id={regulation_id}")
        raise HTTPException(status_code=404, detail="Mapping results not found")
    
    return result


@router.post("/analyze", status_code=202)
async def analyze_mapping(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    규제-제품 매핑 분석을 실행한다 (AI 파이프라인 트리거).

    Args:
        regulation_id (int): 규제 문서 ID.

    Returns:
        dict: 분석 작업 ID 및 상태.
    """
    logger.info(f"POST /mapping/analyze - regulation_id={regulation_id}")
    return await service.analyze_mapping(db, regulation_id)
