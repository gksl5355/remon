# from app.core.models import DataSource, CrawlJob, CrawlLog
# from .base_repository import BaseRepository

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.data_source_model import DataSource, CrawlJob, CrawlLog
from .base_repository import BaseRepository

# class DataSourceRepository(BaseRepository[DataSource]):
#     def __init__(self):
#         super().__init__(DataSource)

class DataSourceRepository(BaseRepository[DataSource]):
    """데이터 소스 Repository"""
    
    def __init__(self):
        super().__init__(DataSource)
    
    async def get_all_websearch_sources(
        self,
        db: AsyncSession
    ) -> List[DataSource]:
        """
        모든 웹 검색 소스 조회
        """
        result = await db.execute(
            select(DataSource)
            .where(DataSource.source_type == "websearch")
            .order_by(DataSource.source_id)
        )
        return list(result.scalars().all())

class CrawlJobRepository(BaseRepository[CrawlJob]):
    def __init__(self):
        super().__init__(CrawlJob)

class CrawlLogRepository(BaseRepository[CrawlLog]):
    def __init__(self):
        super().__init__(CrawlLog)
