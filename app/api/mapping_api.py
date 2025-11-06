"""
module: mapping_api.py
description: Mapping 단계 API 라우터 예시.
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def sample_mapping():
    """Mapping 단계 샘플 엔드포인트."""
    return {"stage": "mapping", "message": "Sample OK"}
