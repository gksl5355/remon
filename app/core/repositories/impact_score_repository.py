from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models import ImpactScore
from app.core.models.enums import RiskLevelEnum
from .base_repository import BaseRepository

class ImpactScoreRepository(BaseRepository[ImpactScore]):
    def __init__(self):
        super().__init__(ImpactScore)
    
    async def get_by_product_and_translation(
        self, db: AsyncSession, product_id: int, translation_id: int
    ) -> Optional[ImpactScore]:
        """제품과 번역 ID로 영향도 점수 조회"""
        result = await db.execute(
            select(ImpactScore).where(
                ImpactScore.product_id == product_id,
                ImpactScore.translation_id == translation_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_high_risk_scores(
        self, db: AsyncSession, product_id: int
    ) -> List[ImpactScore]:
        """특정 제품의 고위험 영향도 조회"""
        result = await db.execute(
            select(ImpactScore).where(
                ImpactScore.product_id == product_id,
                ImpactScore.risk_level == RiskLevelEnum.HIGH
            )
        )
        return result.scalars().all()
