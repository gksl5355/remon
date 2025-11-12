from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.models import Regulation, RegulationVersion, RegulationTranslation
from .base_repository import BaseRepository

class RegulationRepository(BaseRepository[Regulation]):
    def __init__(self):
        super().__init__(Regulation)
    
    async def get_by_country(
        self, db: AsyncSession, country_code: str
    ) -> List[Regulation]:
        """특정 국가의 모든 규제 조회"""
        result = await db.execute(
            select(Regulation).where(Regulation.country_code == country_code)
        )
        return result.scalars().all()
    
    async def get_with_versions(
        self, db: AsyncSession, regulation_id: int
    ) -> Optional[Regulation]:
        """버전 정보를 포함한 규제 조회"""
        result = await db.execute(
            select(Regulation)
            .options(selectinload(Regulation.versions))
            .where(Regulation.regulation_id == regulation_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active_regulations(
        self, db: AsyncSession, country_code: str
    ) -> List[Regulation]:
        """활성 상태의 규제만 조회"""
        result = await db.execute(
            select(Regulation)
            .where(
                Regulation.country_code == country_code,
                Regulation.status == "active"
            )
        )
        return result.scalars().all()

class RegulationVersionRepository(BaseRepository[RegulationVersion]):
    def __init__(self):
        super().__init__(RegulationVersion)
    
    async def get_latest_version(
        self, db: AsyncSession, regulation_id: int
    ) -> Optional[RegulationVersion]:
        """가장 최신 버전 조회"""
        result = await db.execute(
            select(RegulationVersion)
            .where(RegulationVersion.regulation_id == regulation_id)
            .order_by(RegulationVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

class RegulationTranslationRepository(BaseRepository[RegulationTranslation]):
    def __init__(self):
        super().__init__(RegulationTranslation)
    
    async def get_by_language(
        self, db: AsyncSession, version_id: int, language_code: str
    ) -> Optional[RegulationTranslation]:
        """특정 언어의 번역 조회"""
        result = await db.execute(
            select(RegulationTranslation).where(
                RegulationTranslation.regulation_version_id == version_id,
                RegulationTranslation.language_code == language_code
            )
        )
        return result.scalar_one_or_none()
