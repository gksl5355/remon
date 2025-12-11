"""
module: dashboard_service.py
description: 대시보드 구성 비즈니스 로직
author: 조영우
created: 2025-12-11
dependencies:
    - sqlalchemy.ext.asyncio
    - api.dashboard_api.py
"""


import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.crawl_repository import CrawlRepository

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_timeline(self):
        try:
            crawl_repo = CrawlRepository(self.db)
            timeline = await crawl_repo.get_all_crawl_log()
            logger.info(f"Timeline: {timeline}")
            return timeline
        except Exception as e:
            logger.error(f"Error fetching timeline: {e}", exc_info=True)
            return None

    