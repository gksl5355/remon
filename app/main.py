"""
module: main.py
description: FastAPI 엔트리포인트.
"""
from fastapi import FastAPI
from app.api import collect_api, refine_api, mapping_api, report_api, admin_api
from app.config.logger import logger

app = FastAPI(title="KTG Regulation Monitoring")

# 라우터 등록
app.include_router(collect_api.router, prefix="/collect", tags=["Collect"])
app.include_router(refine_api.router, prefix="/refine", tags=["Refine"])
app.include_router(mapping_api.router, prefix="/mapping", tags=["Mapping"])
app.include_router(report_api.router, prefix="/report", tags=["Report"])
app.include_router(admin_api.router, prefix="/admin", tags=["Admin"])

@app.get("/")
async def root():
    """헬스체크용 엔드포인트"""
    logger.info("Health check 호출됨")
    return {"status": "ok"}
