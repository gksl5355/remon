"""
module: ai_api.py
description: AI 파이프라인 실행 API
author: 조영우
created: 2025-12-04
간단 구현
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.ai_pipeline.graph import build_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Pipeline"])


class PipelineRequest(BaseModel):
    regulation_id: int
    product_id: Optional[int] = None
    legacy_regulation_id: Optional[int] = None


@router.post("/pipeline/run")
async def run_pipeline(
    request: PipelineRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    AI 파이프라인 실행
    
    Args:
        regulation_id: 신규 규제 ID
        product_id: 제품 ID (선택)
        legacy_regulation_id: Legacy 규제 ID (선택, 없으면 자동 검색)
    
    Returns:
        파이프라인 실행 결과
    """
    logger.info(f"AI 파이프라인 시작: regulation_id={request.regulation_id}")
    
    try:
        # Graph 빌드
        graph = build_graph()
        
        # State 준비
        state = {
            "change_context": {
                "new_regulation_id": request.regulation_id,
            }
        }
        
        if request.legacy_regulation_id:
            state["change_context"]["legacy_regulation_id"] = request.legacy_regulation_id
        
        if request.product_id:
            state["mapping_filters"] = {
                "product_id": request.product_id
            }
        
        # 파이프라인 실행
        result = await graph.ainvoke(state, {"db_session": db})
        
        # 결과 반환
        return {
            "status": "success",
            "regulation_id": request.regulation_id,
            "change_summary": result.get("change_summary", {}),
            "mapping_results": result.get("mapping_results", {}),
            "impact_scores": result.get("impact_scores", {}),
            "report": result.get("report", {})
        }
        
    except Exception as e:
        logger.error(f"파이프라인 실행 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파이프라인 실행 실패: {str(e)}")
