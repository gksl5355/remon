from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
import json
import os

from app.core.database import get_db
from app.services.report_service import ReportService

router = APIRouter(prefix="/admin/summary", tags=["Admin - Summary"])



# 모든 요약 리포트 목록
@router.get("")
async def list_summary(db: AsyncSession = Depends(get_db)):
    service = ReportService()
    return await service.get_all_summaries(db)


# 특정 리포트 상세 조회
@router.get("/{report_id}")
async def get_summary(report_id: int, db: AsyncSession = Depends(get_db)):
    service = ReportService()
    result = await service.get_summary_by_id(db, report_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    
    return result


# 특정 리포트 수정 (sections 업데이트)
@router.put("/{report_id}")
async def update_summary(report_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    service = ReportService()
    new_sections = body.get("sections")
    
    if not new_sections:
        raise HTTPException(status_code=400, detail="sections가 필요합니다.")
    
    result = await service.update_report(db, report_id, new_sections)
    
    if not result:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    
    return {
        "message": "리포트가 수정되었습니다.",
        "report": result
    }


# DELETE: 리포트 삭제
@router.delete("/{report_id}")
async def delete_summary(report_id: int, db: AsyncSession = Depends(get_db)):
    service = ReportService()
    success = await service.delete_summary(db, report_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 리포트가 없습니다.")
    
    return {"message": "삭제 완료"}


# PDF 다운로드 (임시 더미 파일)
@router.get("/{report_id}/download/pdf")
async def download_pdf(report_id: int):
    dummy_pdf_path = "sample_report.pdf"

    # 더미 PDF 파일 없으면 생성
    if not os.path.exists(dummy_pdf_path):
        with open(dummy_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n% Dummy PDF for demo\n")

    return FileResponse(
        path=dummy_pdf_path,
        filename=f"report_{report_id}.pdf",
        media_type="application/pdf"
    )
