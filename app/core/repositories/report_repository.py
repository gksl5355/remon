from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.models.report_model import Report, ReportItem, ReportSummary
from .base_repository import BaseRepository

class ReportRepository(BaseRepository[Report]):
    """리포트 Repository"""
    
    def __init__(self):
        super().__init__(Report)
    
    async def get_by_regulation_id(
        self,
        db: AsyncSession,
        regulation_id: int
    ) -> Optional[Report]:
        """
        규제 ID로 리포트 조회
        (사실 regulation_id가 아니라 translation_id나 change_id로 조회해야 할 수도 있음)
        """
        result = await db.execute(
            select(Report)
            # 실제 모델 구조에 따라 조건 수정 필요
            .options(
                selectinload(Report.items),
                selectinload(Report.summaries)
            )
            .limit(1)  # 임시
        )
        return result.scalar_one_or_none()
    
    async def get_with_summaries(
        self,
        db: AsyncSession,
        report_id: int
    ) -> Optional[Report]:
        """
        서머리 정보를 포함한 리포트 조회
        """
        result = await db.execute(
            select(Report)
            .options(selectinload(Report.summaries))
            .where(Report.report_id == report_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_summaries(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Report]:
        """
        모든 리포트의 서머리 조회
        """
        result = await db.execute(
            select(Report)
            .options(selectinload(Report.summaries))
            .offset(skip)
            .limit(limit)
            .order_by(Report.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_combined_reports(
        self,
        db: AsyncSession,
        filters: Optional[Dict] = None
    ) -> List[Report]:
        """
        복합 리포트 조회 (필터링 가능)
        """
        query = select(Report).options(
            selectinload(Report.items),
            selectinload(Report.summaries)
        )
        
        if filters:
            if "country_code" in filters:
                query = query.where(Report.country_code == filters["country_code"])
            if "product_id" in filters:
                query = query.where(Report.product_id == filters["product_id"])
        
        result = await db.execute(query)
        return list(result.scalars().all())

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
    
    async def get_by_report_id(
        self,
        db: AsyncSession,
        report_id: int
    ) -> List[ReportSummary]:
        """
        리포트 ID로 서머리 목록 조회
        """
        result = await db.execute(
            select(ReportSummary)
            .where(ReportSummary.report_id == report_id)
        )
        return list(result.scalars().all())


# from typing import List, Optional
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from core.models import Report, ReportItem, ReportSummary
# from .base_repository import BaseRepository

# class ReportRepository(BaseRepository[Report]):
#     def __init__(self):
#         super().__init__(Report)
    
#     async def get_with_items(
#         self, db: AsyncSession, report_id: int
#     ) -> Optional[Report]:
#         """리포트 항목을 포함한 조회"""
#         result = await db.execute(
#             select(Report)
#             .options(
#                 selectinload(Report.items),
#                 selectinload(Report.summaries)
#             )
#             .where(Report.report_id == report_id)
#         )
#         return result.scalar_one_or_none()
    
    
#     async def get_by_country_and_product(
#         self, db: AsyncSession, country_code: str, product_id: int
#     ) -> List[Report]:
#         """국가 및 제품별 리포트 조회"""
#         result = await db.execute(
#             select(Report).where(
#                 Report.country_code == country_code,
#                 Report.product_id == product_id
#             )
#         )
#         return result.scalars().all()
