"""
module: report_service.py
description: 리포트 생성, 조회 및 관련 비즈니스 로직을 처리하는 서비스 계층
author: 조영우
created: 2025-11-10
updated: 2025-11-20
dependencies:
    - sqlalchemy.ext.asyncio
    - core.repositories.report_repository
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from core.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)


class ReportService:
    """리포트 관련 비즈니스 로직을 처리하는 서비스 클래스"""
    
    def __init__(self):
        self.repo = ReportRepository()

    
    async def get_report_detail(self, db: AsyncSession, regulation_id: int) -> dict | None:
        """
        리포트 상세 정보를 조회한다 (프론트 형식).

        Args:
            db (AsyncSession): 데이터베이스 세션.
            regulation_id (int): 규제 문서 ID.

        Returns:
            dict | None: 리포트 상세 정보 또는 None.
        """
        logger.info(f"Fetching report detail: regulation_id={regulation_id}")
        
        try:
            report = await self.repo.get_by_regulation_id(db, regulation_id)
            
            if not report:
                logger.warning(f"Report not found: regulation_id={regulation_id}")
                return None
            
            # JSONB에서 직접 가져오기
            if report.summaries and len(report.summaries) > 0:
                summary_data = report.summaries[0].summary_text
                
                if summary_data:
                    # JSONB 데이터 그대로 반환 (배열 형식)
                    return {
                        "regulation_id": regulation_id,
                        "title": "리포트 제목",
                        "last_updated": report.created_at.isoformat() if report.created_at else None,
                        "sections": summary_data  # 이미 배열 형식으로 순서 보장
                    }
            
            # JSONB 데이터가 없으면 None 반환
            logger.warning(f"No summary data found for regulation_id={regulation_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching report detail: {e}", exc_info=True)
            return None

    async def create_report(
        self,
        db: AsyncSession,
        regulation_id: int,
        report_type: str
    ) -> dict:
        """
        리포트 생성을 요청한다 (AI 파이프라인 트리거).

        Args:
            db (AsyncSession): 데이터베이스 세션.
            regulation_id (int): 규제 문서 ID.
            report_type (str): 리포트 타입 (summary/comprehensive).

        Returns:
            dict: 생성된 리포트 ID 및 상태.
        """
        logger.info(f"Creating report for regulation_id={regulation_id}, type={report_type}")
        
        async with db.begin():
            # TODO: AI1(고서아) - ai_service.generate_report() 호출
            pass
        
        return {"report_id": None, "status": "pending"}

    async def update_report(
        self,
        db: AsyncSession,
        report_id: int,
        update_data: dict
    ) -> dict | None:
        """
        리포트 내용을 수정한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            report_id (int): 리포트 ID.
            update_data (dict): 수정할 데이터.

        Returns:
            dict | None: 수정된 리포트 정보 또는 None.
        """
        logger.info(f"Updating report: report_id={report_id}")
        
        try:
            async with db.begin():
                updated = await self.repo.update(db, report_id, update_data)
                if updated:
                    logger.info(f"Report updated: report_id={report_id}")
                    return {"report_id": updated.report_id, "status": "updated"}
                return None
        except Exception as e:
            logger.error(f"Error updating report: {e}", exc_info=True)
            return None

    async def delete_report(self, db: AsyncSession, report_id: int) -> bool:
        """
        리포트를 삭제한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            report_id (int): 리포트 ID.

        Returns:
            bool: 삭제 성공 여부.
        """
        logger.info(f"Deleting report: report_id={report_id}")
        
        try:
            async with db.begin():
                success = await self.repo.delete(db, report_id)
                logger.info(f"Report deleted: report_id={report_id}, success={success}")
                return success
        except Exception as e:
            logger.error(f"Error deleting report: {e}", exc_info=True)
            return False

    async def download_report(self, db: AsyncSession, report_id: int) -> bytes | None:
        """
        리포트를 PDF/Excel 파일로 다운로드한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            report_id (int): 리포트 ID.

        Returns:
            bytes | None: 파일 바이너리 데이터 또는 None.
        """
        logger.info(f"Downloading report: report_id={report_id}")
        
        # TODO: 리포트 데이터 조회
        # TODO: PDF/Excel 생성 (reportlab, openpyxl 등)
        
        return None
