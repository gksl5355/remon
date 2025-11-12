from app.core.models import DataSource, CrawlJob, CrawlLog
from .base_repository import BaseRepository

class DataSourceRepository(BaseRepository[DataSource]):
    def __init__(self):
        super().__init__(DataSource)

class CrawlJobRepository(BaseRepository[CrawlJob]):
    def __init__(self):
        super().__init__(CrawlJob)

class CrawlLogRepository(BaseRepository[CrawlLog]):
    def __init__(self):
        super().__init__(CrawlLog)
