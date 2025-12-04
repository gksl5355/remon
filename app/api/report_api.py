# app/api/report_api.py
"""
module: report_api.py
description: 리포트 조회, 생성, 수정, 삭제 및 다운로드 API
author: 조영우 (박성연frontend 브랜치에서 merge함)
merge_dated: 2025-11-12
"""

import logging
import io
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.report_service import ReportService


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Reports"])
service = ReportService()

# 더미 데이터 제거됨 (2025-11-12)

# 기간별 종합 리포트 다운로드
@router.get("/reports/combined/download")
async def download_combined_report(
    start_date: str,
    end_date: str,
    db: AsyncSession = Depends(get_db)
):
    data = await service.download_combined_report(start_date, end_date, db)
    content = data["content"]
    filename = data["filename"]
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# 규제별 요약 리포트 조회
@router.get("/reports/{regulation_id}")
async def get_report(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    규제별 요약 리포트를 조회한다.
    
    Args:
        regulation_id (int): 규제 문서 ID.
        
    Returns:
        dict: 리포트 상세 정보.
        
    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /reports/{regulation_id}")
    report = await service.get_report_detail(db, regulation_id)
    
    if not report:
        logger.warning(f"Report not found: regulation_id={regulation_id}")
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


# 리포트 다운로드 (PDF)
@router.get("/reports/{regulation_id}/download")
async def download_report(
    regulation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    리포트를 PDF 파일로 다운로드한다.
    
    Args:
        regulation_id (int): 규제 문서 ID.
        
    Returns:
        FileResponse: PDF 파일.
        
    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /reports/{regulation_id}/download")
    
    pdf_bytes = await service.download_report(db, regulation_id)
    
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Report not found")
    
    filename = f"report_{regulation_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    리포트를 삭제한다.

    Args:
        report_id (int): 리포트 ID.

    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"DELETE /reports/{report_id}")
    success = await service.delete_report(db, report_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")

@router.patch("/reports/{report_id}")
async def update_report(
    report_id: int,
    update_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    리포트 내용을 수정한다.

    Args:
        report_id (int): 리포트 ID.
        update_data (dict): 수정할 데이터.

    Returns:
        dict: 수정된 리포트 정보.

    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"PATCH /reports/{report_id}")
    updated = await service.update_report(db, report_id, update_data)
    
    if not updated:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return updated

@router.post("/reports", status_code=201)
async def create_report(
    regulation_id: int,
    report_type: str = "summary",
    db: AsyncSession = Depends(get_db)
):
    """
    (종합?)리포트 생성을 요청한다 (AI 파이프라인 트리거).

    Args:
        regulation_id (int): 규제 문서 ID.
        report_type (str): 리포트 타입 (summary/comprehensive).

    Returns:
        dict: 생성된 리포트 ID 및 상태.
    """
    logger.info(f"POST /reports - regulation_id={regulation_id}, type={report_type}")
    return await service.create_report(db, regulation_id, report_type)
