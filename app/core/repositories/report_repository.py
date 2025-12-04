from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from app.core.models.report_model import Report, ReportItem, ReportSummary
from app.core.schemas.report_schema import ReportCreate
from .base_repository import BaseRepository
class ReportRepository:
    
    # --- Report ---
    async def create_report(self, db: AsyncSession, report_data: ReportCreate) -> Report:
        db_report = Report(**report_data.model_dump())
        db.add(db_report)
        await db.commit()
        await db.refresh(db_report)
        return db_report

    async def get_report(self, db: AsyncSession, report_id: int) -> Optional[Report]:
        # 주의: 예전에는 .options(joinedload(Report.summary)) 등을 썼겠지만
        # 이제는 summary와 FK 연결이 끊겨서 join이 불가능합니다.
        query = select(Report).where(Report.report_id == report_id)
        result = await db.execute(query)
        return result.scalars().first()

    async def create_with_items(
        self, 
        db: AsyncSession, 
        report_data: dict, 
        items_data: List[dict],
        summaries_data: List[dict]
    ) -> Report:
        """리포트와 항목들을 함께 생성"""
        # Report 생성
        report = Report(**report_data)
        db.add(report)
        await db.flush()
        
        # Items 생성
        for item_data in items_data:
            item = ReportItem(**item_data, report_id=report.report_id)
            db.add(item)
        
        # Summaries 생성
        for summary_data in summaries_data:
            summary = ReportSummary(**summary_data, report_id=report.report_id)
            db.add(summary)
        
        await db.flush()
        await db.refresh(report)
        return report
    
class ReportSummaryRepository(BaseRepository[ReportSummary]):
    """리포트 서머리 Repository"""
    
    def __init__(self):
        super().__init__(ReportSummary)
    
    async def create_report_summary(
        self,
        db: AsyncSession,
        summary_data: dict
    ) -> ReportSummary:
        """
        ReportSummary만 단독 생성
        
        Args:
            db: 데이터베이스 세션
            summary_data: sections JSON (배열)
        
        Returns:
            생성된 ReportSummary 객체
        """
        summary = ReportSummary(summary_text=summary_data)
        db.add(summary)
        await db.flush()
        await db.refresh(summary)
        return summary
    
    async def get_by_summary_id(
        self,
        db: AsyncSession,
        summary_id: int
    ) -> Optional[ReportSummary]:
        """
        summary_id로 서머리 조회
        """
        result = await db.execute(
            select(ReportSummary)
            .where(ReportSummary.summary_id == summary_id)
        )
        return result.scalars().first()
