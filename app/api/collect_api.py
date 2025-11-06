"""
module: collect_api.py
description: Collect 단계 API 라우터 예시.
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def sample_collect():
    """Collect 단계 샘플 엔드포인트."""
    return {"stage": "collect", "message": "Sample OK"}
