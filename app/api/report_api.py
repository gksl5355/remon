"""
module: report_api.py
description: 리포트 조회, 생성, 수정, 삭제 및 다운로드 API
author: 조영우
created: 2025-11-10
updated: 2025-11-10
dependencies:
    - fastapi
    - app.services.report_service
    - app.core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["Reports"])
service = ReportService()


@router.get("/")
async def list_reports(
    country: str | None = Query(None, description="국가 필터 (예: KR, US)"),
    risk_level: str | None = Query(None, description="영향도 필터 (low/medium/high)"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    db: AsyncSession = Depends(get_db)
):
    """
    리포트 목록을 조회한다.

    Returns:
        dict: 리포트 목록 및 페이지네이션 정보.
    """
    logger.info(f"GET /reports - country={country}, risk_level={risk_level}, page={page}")
    return await service.get_reports(db, country, risk_level, page, page_size)


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    리포트 상세 정보를 조회한다.

    Args:
        report_id (int): 리포트 ID.

    Returns:
        dict: 리포트 상세 정보.

    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /reports/{report_id}")
    report = await service.get_report_detail(db, report_id)
    
    if not report:
        logger.warning(f"Report not found: report_id={report_id}")
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@router.post("/", status_code=201)
async def create_report(
    regulation_id: int,
    report_type: str = "summary",
    db: AsyncSession = Depends(get_db)
):
    """
    리포트 생성을 요청한다 (AI 파이프라인 트리거).

    Args:
        regulation_id (int): 규제 문서 ID.
        report_type (str): 리포트 타입 (summary/comprehensive).

    Returns:
        dict: 생성된 리포트 ID 및 상태.
    """
    logger.info(f"POST /reports - regulation_id={regulation_id}, type={report_type}")
    return await service.create_report(db, regulation_id, report_type)


@router.patch("/{report_id}")
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


@router.delete("/{report_id}", status_code=204)
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


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    리포트를 PDF 파일로 다운로드한다.

    Args:
        report_id (int): 리포트 ID.

    Returns:
        dict: 다운로드 정보 (TODO: 실제 파일 스트림).

    Raises:
        HTTPException: 리포트를 찾을 수 없는 경우 404.
    """
    logger.info(f"GET /reports/{report_id}/download")
    file_data = await service.download_report(db, report_id)
    
    if not file_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"message": "Download feature coming soon", "report_id": report_id}
