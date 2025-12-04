from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from app.core.models.report_model import Report, ReportItem, ReportSummary
from app.core.schemas.report_schema import ReportCreate

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

    # --- Report Item ---
    async def create_report_item(self, db: AsyncSession, item_data: dict) -> ReportItem:
        db_item = ReportItem(**item_data)
        db.add(db_item)
        await db.commit()
        await db.refresh(db_item)
        return db_item

    # --- [핵심 수정] Report Summary (JSONB 적용) ---
    async def create_summary(self, db: AsyncSession, summary_text: Dict[str, Any]) -> ReportSummary:
        """
        [수정됨] report_id, impact_score_id 등 연결 고리가 사라지고
        오직 JSON 데이터(summary_text)만 저장합니다.
        """
        db_summary = ReportSummary(
            summary_text=summary_text  # JSONB 컬럼
        )
        db.add(db_summary)
        await db.commit()
        await db.refresh(db_summary)
        return db_summary

    async def get_summary(self, db: AsyncSession, summary_id: int) -> Optional[ReportSummary]:
        query = select(ReportSummary).where(ReportSummary.summary_id == summary_id)
        result = await db.execute(query)
        return result.scalars().first()
