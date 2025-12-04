
# 임포트 추가
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.core.models.glossary_model import GlossaryTerm
from .base_repository import BaseRepository



class GlossaryTermRepository(BaseRepository[GlossaryTerm]):
    def __init__(self):
        super().__init__(GlossaryTerm)

# 추가

    async def get_by_language(
        self,
        db: AsyncSession,
        language_code: str
    ) -> List[GlossaryTerm]:
        """특정 언어의 용어 조회"""
        result = await db.execute(
            select(GlossaryTerm).where(
                GlossaryTerm.language_code == language_code
            )
        )
        return list(result.scalars().all())
    
    async def search_term(
        self,
        db: AsyncSession,
        keyword: str,
        language_code: str
    ) -> List[GlossaryTerm]:
        """
        키워드로 용어 검색 (RefineAgent용)
        
        Args:
            keyword: 검색 키워드
            language_code: 언어 코드
        
        Returns:
            매칭되는 용어 리스트
        """
        from sqlalchemy import or_, func
        
        result = await db.execute(
            select(GlossaryTerm).where(
                GlossaryTerm.language_code == language_code,
                or_(
                    func.lower(GlossaryTerm.canonical_key).contains(keyword.lower()),
                    func.lower(GlossaryTerm.synonyms).contains(keyword.lower())
                )
            )
        )
        return list(result.scalars().all())