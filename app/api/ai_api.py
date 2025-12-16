"""
module: ai_api.py
description: AI 파이프라인 실행 및 HITL API
author: 조영우
created: 2025-12-04
updated: 2025-01-23 (HITL 통합)
dependencies:
    - fastapi
    - app.core.database
    - app.ai_pipeline.nodes.hitl
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from scripts import run_full_pipeline
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Pipeline"])


# ==================== Request Models ====================

class HITLFeedbackRequest(BaseModel):
    """HITL 피드백 요청"""
    regulation_id: int
    user_message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "regulation_id": 123,
                "user_message": "매핑을 다시 해줘, 니코틴 feature가 잘못됐어"
            }
        }


# ==================== Pipeline Endpoints ====================

@router.post("/pipeline/run")
async def run_pipeline(citation_code: str = "21 CFR Part 1160"):
    """AI 파이프라인 실행"""
    try:
        logger.info(f"AI 파이프라인 시작: citation_code={citation_code}")
        await run_full_pipeline.run_full_pipeline(citation_code)
        return {"status": "success", "message": "파이프라인 실행 완료"}
    except Exception as e:
        logger.error(f"파이프라인 실행 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파이프라인 실행 실패: {str(e)}")


# ==================== HITL Endpoints ====================

@router.post("/hitl/feedback")
async def submit_hitl_feedback(
    request: HITLFeedbackRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    HITL 피드백 제출 및 파이프라인 재실행
    
    사용자 메시지를 받아 intent 분류 후:
    - question: 답변만 반환
    - modification: 파이프라인 재실행
    """
    try:
        from app.ai_pipeline.nodes.hitl import classify_intent, detect_target_node, refine_hitl_feedback
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        
        repo = IntermediateOutputRepository()
        
        # 중간 결과물 존재 여부 확인
        intermediate_data = await repo.get_intermediate(
            db,
            regulation_id=request.regulation_id
        )
        
        if not intermediate_data:
            raise HTTPException(
                status_code=404,
                detail=f"regulation_id={request.regulation_id}의 분석 결과가 없습니다. 먼저 파이프라인을 실행하세요."
            )
        
        # Intent 분류
        intent_result = classify_intent(request.user_message)
        intent = intent_result["intent"]
        
        logger.info(
            f"✅ HITL 피드백 수신: regulation_id={request.regulation_id}, "
            f"intent={intent}, message={request.user_message[:50]}..."
        )
        
        if intent == "question":
            # 질문 처리: 답변만 반환 (재실행 없음)
            from app.ai_pipeline.nodes.hitl import answer_question
            from app.ai_pipeline.state import AppState
            
            # State 복원 (간단 버전)
            state = AppState(
                regulation={"regulation_id": request.regulation_id},
                **intermediate_data
            )
            
            answer = await answer_question(state, request.user_message)
            
            return {
                "status": "answered",
                "intent": "question",
                "regulation_id": request.regulation_id,
                "answer": answer
            }
        
        else:  # modification
            # 수정 처리: target_node 식별 및 피드백 정제
            target_node = detect_target_node(request.user_message)
            cleaned_feedback = refine_hitl_feedback(request.user_message, target_node)
            
            logger.info(
                f"🔄 HITL 수정 요청: target_node={target_node}, "
                f"cleaned_feedback={cleaned_feedback}"
            )
            
            return {
                "status": "accepted",
                "intent": "modification",
                "regulation_id": request.regulation_id,
                "target_node": target_node,
                "message": f"{target_node} 노드 재실행이 필요합니다. 파이프라인을 다시 실행하세요."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ HITL 피드백 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hitl/status/{regulation_id}")
async def get_hitl_status(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    HITL 상태 조회 (중간 결과물 존재 여부)
    """
    try:
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        
        repo = IntermediateOutputRepository()
        intermediate_data = await repo.get_intermediate(db, regulation_id=regulation_id)
        
        if not intermediate_data:
            return {
                "regulation_id": regulation_id,
                "has_data": False,
                "available_nodes": []
            }
        
        available_nodes = list(intermediate_data.keys())
        
        logger.info(
            f"✅ HITL 상태 조회: regulation_id={regulation_id}, "
            f"nodes={available_nodes}"
        )
        
        return {
            "regulation_id": regulation_id,
            "has_data": True,
            "available_nodes": available_nodes
        }
        
    except Exception as e:
        logger.error(f"❌ HITL 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
