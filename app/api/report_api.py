"""
module: report_api.py
description: Report 단계 API 라우터 예시.
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def sample_report():
    """Report 단계 샘플 엔드포인트."""
    return {"stage": "report", "message": "Sample OK"}
