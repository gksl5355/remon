"""
regulation_keynote_repository.py
RegulationChangeKeynote 테이블 Repository
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.regulation_model import RegulationChangeKeynote
from app.core.repositories.base_repository import BaseRepository


class RegulationKeynoteRepository(BaseRepository[RegulationChangeKeynote]):
    """RegulationChangeKeynote Repository"""
    
    def __init__(self):
        super().__init__(RegulationChangeKeynote)
    
    async def create_keynote(
        self,
        db: AsyncSession,
        keynote_data: dict
    ) -> RegulationChangeKeynote:
        """
        Keynote 생성
        
        Args:
            db: 데이터베이스 세션
            keynote_data: keynote JSON 데이터
        
        Returns:
            생성된 RegulationChangeKeynote 객체
        """
        keynote = RegulationChangeKeynote(keynote_text=keynote_data)
        db.add(keynote)
        await db.flush()
        await db.refresh(keynote)
        return keynote
    
    async def get_all_keynotes(
        self,
        db: AsyncSession,
        country: Optional[str] = None
    ) -> List[RegulationChangeKeynote]:
        """
        모든 keynote 조회 (국가 필터 옵션)
        
        Args:
            db: 데이터베이스 세션
            country: 국가 코드 필터 (옵션)
        
        Returns:
            RegulationChangeKeynote 리스트
        """
        query = select(RegulationChangeKeynote)
        
        # 국가 필터 (JSONB 쿼리)
        if country:
            query = query.where(
                RegulationChangeKeynote.keynote_text['country'].astext == country
            )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def get_keynote_by_id(
        self,
        db: AsyncSession,
        keynote_id: int
    ) -> Optional[RegulationChangeKeynote]:
        """
        ID로 keynote 조회
        
        Args:
            db: 데이터베이스 세션
            keynote_id: keynote ID
        
        Returns:
            RegulationChangeKeynote 또는 None
        """
        result = await db.execute(
            select(RegulationChangeKeynote).where(
                RegulationChangeKeynote.keynote_id == keynote_id
            )
        )
        return result.scalar_one_or_none()
