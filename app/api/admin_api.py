"""
module: admin_api.py
description: Admin 단계 API 라우터 예시.
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def sample_admin():
    """Admin 단계 샘플 엔드포인트."""
    return {"stage": "admin", "message": "Sample OK"}
