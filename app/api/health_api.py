"""
module: health_api.py
description: 헬스체크용 API
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/")
async def health_check():
    """
    헬스체크 + 날짜/시간/언어/다크모드 상태 반환
    (프론트 HeaderBar.vue에서 사용)
    """
    return {
        "status": "ok",
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "language": "ko",
        "dark_mode": False
    }
