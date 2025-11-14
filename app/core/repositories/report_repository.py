from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.models import Report, ReportItem, ReportSummary
from .base_repository import BaseRepository

class ReportRepository(BaseRepository[Report]):
    def __init__(self):
        super().__init__(Report)
    
    async def get_with_items(
        self, db: AsyncSession, report_id: int
    ) -> Optional[Report]:
        """리포트 항목을 포함한 조회"""
        result = await db.execute(
            select(Report)
            .options(
                selectinload(Report.items),
                selectinload(Report.summaries)
            )
            .where(Report.report_id == report_id)
        )
        return result.scalar_one_or_none()
    
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
    
    async def get_by_country_and_product(
        self, db: AsyncSession, country_code: str, product_id: int
    ) -> List[Report]:
        """국가 및 제품별 리포트 조회"""
        result = await db.execute(
            select(Report).where(
                Report.country_code == country_code,
                Report.product_id == product_id
            )
        )
        return result.scalars().all()
