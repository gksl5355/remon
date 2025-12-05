from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.repositories.base_repository import BaseRepository
from app.core.models.regulation_model import RegulationTranslation


class TranslationRepository(BaseRepository[RegulationTranslation]):
    """regulation_translations 테이블용 Repository"""

    def __init__(self):
        super().__init__(RegulationTranslation)

    async def get_by_version_and_language(
        self, db: AsyncSession, version_id: int, language_code: str
    ) -> Optional[RegulationTranslation]:
        result = await db.execute(
            select(RegulationTranslation).where(
                RegulationTranslation.regulation_version_id == version_id,
                RegulationTranslation.language_code == language_code,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, db: AsyncSession, translation_id: int
    ) -> Optional[RegulationTranslation]:
        result = await db.execute(
            select(RegulationTranslation).where(
                RegulationTranslation.translation_id == translation_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert_translation(
        self,
        db: AsyncSession,
        *,
        version_id: int,
        language_code: str,
        translated_text: Optional[str] = None,
        glossary_term_id: Optional[str] = None,
        translation_status: str = "queued",
        s3_key: Optional[str] = None,
    ) -> RegulationTranslation:
        """
        존재하면 업데이트, 없으면 생성.
        """
        existing = await self.get_by_version_and_language(db, version_id, language_code)
        if existing:
            return await self.update(
                db,
                existing.translation_id,
                translated_text=translated_text,
                glossary_term_id=glossary_term_id or existing.glossary_term_id,
                translation_status=translation_status,
                s3_key=s3_key or existing.s3_key,
            )

        return await self.create(
            db,
            regulation_version_id=version_id,
            language_code=language_code,
            translated_text=translated_text,
            glossary_term_id=glossary_term_id,
            translation_status=translation_status,
            s3_key=s3_key,
        )
