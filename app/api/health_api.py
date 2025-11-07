"""
module: health_api.py
description: 헬스체크용 API
"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def health():
    """서버 상태 확인"""
    return {"status": "healthy"}
