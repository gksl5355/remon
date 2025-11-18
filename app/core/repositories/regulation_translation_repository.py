# app/core/repositories/regulation_translation_repository.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.regulation_model import RegulationTranslation
from .base_repository import BaseRepository

class RegulationTranslationRepository(BaseRepository[RegulationTranslation]):
    """
    규제 번역 Repository
    
    RefineAgent가 번역을 저장할 때 사용
    """
    
    def __init__(self):
        super().__init__(RegulationTranslation)
    
    async def get_by_version_and_language(
        self,
        db: AsyncSession,
        regulation_version_id: int,
        language_code: str
    ) -> Optional[RegulationTranslation]:
        """
        버전 ID와 언어 코드로 번역 조회
        
        Args:
            regulation_version_id: 규제 버전 ID
            language_code: 언어 코드 (예: 'ko', 'en')
        
        Returns:
            번역 객체 또는 None
        """
        result = await db.execute(
            select(RegulationTranslation).where(
                RegulationTranslation.regulation_version_id == regulation_version_id,
                RegulationTranslation.language_code == language_code
            )
        )
        return result.scalar_one_or_none()
    
    async def create_or_update_translation(
        self,
        db: AsyncSession,
        regulation_version_id: int,
        language_code: str,
        translated_text: str,
        **kwargs
    ) -> RegulationTranslation:
        """
        번역 생성 또는 업데이트
        
        RefineAgent가 번역을 저장할 때 사용
        """
        # 기존 번역 확인
        existing = await self.get_by_version_and_language(
            db, regulation_version_id, language_code
        )
        
        if existing:
            # 업데이트
            return await self.update(
                db,
                existing.translation_id,
                translated_text=translated_text,
                **kwargs
            )
        else:
            # 생성
            return await self.create(
                db,
                regulation_version_id=regulation_version_id,
                language_code=language_code,
                translated_text=translated_text,
                **kwargs
            )
