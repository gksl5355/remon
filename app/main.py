"""
module: main.py
description: FastAPI 엔트리포인트 (라우터 등록 + 세션 DI)
"""
from fastapi import FastAPI
from app.api import health_api, report_api
from app.config.logger import logger

app = FastAPI(title="remon API")

app.include_router(health_api.router, prefix="/health", tags=["Health"])
app.include_router(report_api.router, prefix="/report", tags=["Report"])

@app.get("/")
async def root():
    """기본 헬스체크"""
    logger.info("Health check 호출됨")
    return {"status": "ok"}
