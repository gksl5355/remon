from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import regulation_api, report_api, auth_api
from app.api.admin import admin_regulation_api, admin_summary_api, admin_websearch_api

app = FastAPI(
    title="REMON Regulatory Monitoring API",
    description="Demo backend for Regulation Summary Reports (Admin + User)",
    version="1.3.0"
)

# CORS 설정 (프론트 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 메인 페이지 엔드포인트
app.include_router(regulation_api.router, prefix="/api")
app.include_router(report_api.router, prefix="/api")
app.include_router(auth_api.router, prefix="/api")

#관리자 페이지 엔드포인트
app.include_router(admin_regulation_api.router, prefix="/api")
app.include_router(admin_summary_api.router, prefix="/api")
app.include_router(admin_websearch_api.router, prefix="/api")
# app.include_router(collect_api.router, prefix="/api")
# app.include_router(mapping_api.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "✅ REMON FastAPI backend running with Admin APIs!"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "FastAPI server running"}