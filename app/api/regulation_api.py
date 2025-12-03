<<<<<<< HEAD
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Regulations"])

# 규제 목록
REGULATIONS = [
    {"id": 1, "impact": "높음", "country": "EU", "category": "라벨 표시", "summary": "니코틴 함량 표기 기준 강화 (EU Directive 2025/127)"},
    {"id": 2, "impact": "보통", "country": "US", "category": "광고 규제", "summary": "전자담배 광고 규제 완화 및 청소년 보호 가이드라인 개정"},
    {"id": 3, "impact": "긴급", "country": "US", "category": "광고 규제", "summary": "전자담배 광고 규제 완화 및 청소년 보호 가이드라인 개정"},
]

@router.get("/regulations")
def get_regulations():
    return {"today_count": len(REGULATIONS), "regulations": REGULATIONS}

@router.get("/regulations/{regulation_id}")
def get_regulation(regulation_id: int):
    reg = next((r for r in REGULATIONS if r["id"] == regulation_id), None)
    if not reg:
        raise HTTPException(status_code=404, detail="Regulation not found")
=======
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
    
>>>>>>> origin/main
    return reg
