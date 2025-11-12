"""
module: regulation_service.py
description: 규제 문서 조회 비즈니스 로직
author: 조영우
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - sqlalchemy.ext.asyncio
    - core.repositories.regulation_repository
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from core.repositories.regulation_repository import RegulationRepository

logger = logging.getLogger(__name__)


class RegulationService:
    """규제 문서 관련 비즈니스 로직을 처리하는 서비스 클래스"""

    def __init__(self):
        self.repo = RegulationRepository()

    async def get_regulations(self, db: AsyncSession, country: str | None = None) -> dict:
        """
        규제 문서 목록을 조회한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            country (str | None): 국가 필터.

        Returns:
            dict: 규제 문서 목록 (프론트 형식).
        """
        logger.info(f"Fetching regulations - country={country}")
        
        try:
            # Repository 호출
            if country:
                regulations = await self.repo.get_by_country(db, country)
            else:
                regulations = await self.repo.get_multi(db, skip=0, limit=100)
            
            # 프론트 형식으로 변환
            result = []
            for reg in regulations:
                result.append({
                    "id": reg.regulation_id,
                    "country": reg.country_code,
                    "title": reg.title or "제목 없음",
                    "status": reg.status or "active",
                    # TODO: impact, category는 ImpactScore 테이블에서 가져와야 함
                    "impact": "보통",  # 임시값
                    "category": "기타",  # 임시값
                    "summary": reg.title or ""
                })
            
            logger.info(f"Found {len(result)} regulations")
            return {
                "today_count": len(result),
                "regulations": result
            }
            
        except Exception as e:
            logger.error(f"Error fetching regulations: {e}", exc_info=True)
            # 에러 발생해도 빈 배열 반환
            return {
                "today_count": 0,
                "regulations": []
            }

    async def get_regulation_detail(
        self, 
        db: AsyncSession, 
        regulation_id: int
    ) -> dict | None:
        """
        규제 문서 상세 정보를 조회한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            regulation_id (int): 규제 문서 ID.

        Returns:
            dict | None: 규제 문서 상세 정보 또는 None.
        """
        logger.info(f"Fetching regulation detail: regulation_id={regulation_id}")
        
        try:
            # Repository 호출
            regulation = await self.repo.get_with_versions(db, regulation_id)
            
            if not regulation:
                logger.warning(f"Regulation not found: regulation_id={regulation_id}")
                return None
            
            # 프론트 형식으로 변환
            return {
                "id": regulation.regulation_id,
                "country": regulation.country_code,
                "title": regulation.title or "제목 없음",
                "status": regulation.status or "active",
                "impact": "보통",  # 임시값
                "category": "기타",  # 임시값
                "summary": regulation.title or "",
                "created_at": regulation.created_at.isoformat() if regulation.created_at else None
            }
            
        except Exception as e:
            logger.error(f"Error fetching regulation detail: {e}", exc_info=True)
            return None
