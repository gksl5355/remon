from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import regulation_api, report_api, ai_api, translation_api
from app.api.admin import admin_s3_api

app = FastAPI(
    title="REMON Regulatory Monitoring API",
    description="Demo backend for Regulation Summary Reports (Admin + User)",
    version="1.3.0"
)

# CORS 설정 (프론트 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 메인 페이지 엔드포인트
app.include_router(regulation_api.router, prefix="/api")
app.include_router(report_api.router, prefix="/api")
app.include_router(ai_api.router, prefix="/api")
app.include_router(translation_api.router, prefix="/api")

#관리자 페이지 엔드포인트
app.include_router(admin_s3_api.router, prefix="/api/admin/s3", tags=["Admin-S3"])

@app.get("/")
def root():
    return {"message": "✅ REMON FastAPI backend running with Admin APIs!"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "FastAPI server running"}
