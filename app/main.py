"""
module: main.py
description: FastAPI 엔트리포인트 (라우터 등록 + 세션 DI)
author: 조영우
created: 2025-11-10
updated: 2025-11-11
"""
from fastapi import FastAPI
from app.api import sample_api, report_api, admin_api, mapping_api, collect_api, auth_api, health_api
from app.config.logger import logger

app = FastAPI(
    title="REMON API",
    description="규제 모니터링 및 매핑 시스템",
    version="0.1.0"
)

# 라우터 등록
app.include_router(sample_api.router)
# app.include_router(auth_api.router)
# app.include_router(collect_api.router)
# app.include_router(report_api.router)
# app.include_router(admin_api.router)
# app.include_router(mapping_api.router) # 미구현 목록 주석처리 함
app.include_router(health_api.router, prefix="/health", tags=["Health"])

@app.get("/")
async def root():
    """기본 헬스체크"""
    logger.info("Health check 호출됨")
    return {"status": "ok"}
