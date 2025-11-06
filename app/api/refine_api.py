"""
module: refine_api.py
description: Refine 단계 API 라우터 예시.
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def sample_refine():
    """Refine 단계 샘플 엔드포인트."""
    return {"stage": "refine", "message": "Sample OK"}
