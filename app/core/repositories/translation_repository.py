"""
module: translation_repository.py
description: Report 번역 저장 Repository (report_summaries.translation 컬럼 사용)
author: AI Agent
created: 2025-01-22
updated: 2025-01-22
dependencies:
    - sqlalchemy.ext.asyncio
    - app.core.models.report_model
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.models.report_model import ReportSummary


class ReportTranslationRepository:
    """Report 번역 저장 Repository"""
    
    async def save_translation(
        self,
        db: AsyncSession,
        summary_id: int,
        translated_sections: dict
    ) -> ReportSummary:
        """
        번역된 보고서를 report_summaries.translation에 저장.
        
        Args:
            db: 데이터베이스 세션
            summary_id: ReportSummary ID
            translated_sections: 번역된 sections JSON
        
        Returns:
            업데이트된 ReportSummary
        """
        await db.execute(
            update(ReportSummary)
            .where(ReportSummary.summary_id == summary_id)
            .values(translation=translated_sections)
        )
        await db.flush()
        
        result = await db.execute(
            select(ReportSummary).where(ReportSummary.summary_id == summary_id)
        )
        return result.scalar_one()
    
    async def get_translation(
        self,
        db: AsyncSession,
        summary_id: int
    ) -> Optional[dict]:
        """
        저장된 번역 조회.
        
        Args:
            db: 데이터베이스 세션
            summary_id: ReportSummary ID
        
        Returns:
            번역 JSON 또는 None
        """
        result = await db.execute(
            select(ReportSummary.translation)
            .where(ReportSummary.summary_id == summary_id)
        )
        return result.scalar_one_or_none()


__all__ = ["ReportTranslationRepository"]
