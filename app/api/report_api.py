"""
module: report_api.py
description: 리포트 관련 API 라우터
"""
from fastapi import APIRouter
from app.services.report_service import ReportService

router = APIRouter()
service = ReportService()

@router.post("/generate")
async def generate_report(request: dict):
    """리포트 생성 API"""
    return await service.generate_report(request)
