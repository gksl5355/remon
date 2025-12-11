import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional


from app.core.models.data_source_model import CrawlLog

class CrawlRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.local_backup_dir = "db"


    # async def get_all_crawl_log(self):
    #     """
    #     타임라인 불러오는 repo함수 12-11 현재는 데이터 비어있음
    #     """
    #     query = select(CrawlLog)
    #     result = await self.db.execute(query)
    #     return result.scalar_one_or_none()