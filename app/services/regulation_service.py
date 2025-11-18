"""
module: regulation_service.py
description: 규제 문서 조회 비즈니스 로직
author: 조영우
created: 2025-11-12
updated: 2025-11-14
dependencies:
    - sqlalchemy.ext.asyncio
    - core.repositories.regulation_repository
"""

from config.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from core.repositories.regulation_repository import RegulationRepository

# logger = logging.getLogger(__name__)


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
        
        # risk_level 한글 변환 맵
        RISK_LEVEL_MAP = {
            "LOW": "낮음",
            "MEDIUM": "보통",
            "HIGH": "높음"
        }
        
        try:
            # keynote와 impact_score를 포함하여 조회
            regulations = await self.repo.get_with_keynotes_and_impact(db, country)
            
            # 프론트 형식으로 변환
            result = []
            for reg in regulations:
                # 최신 버전의 첫 번째 keynote 가져오기
                keynote = None
                if reg.versions:
                    latest_version = reg.versions[-1]
                    if latest_version.keynotes:
                        keynote = latest_version.keynotes[0]
                
                # keynote에서 impact, category, summary 모두 추출
                if keynote and keynote.impact_score:
                    impact = RISK_LEVEL_MAP.get(keynote.impact_score.risk_level, "보통")
                    category = keynote.regulation_type 
                    summary = keynote.title 
                else:
                    impact = "보통"
                    category = "기타"
                    summary = reg.title or ""
                
                result.append({
                    "id": reg.regulation_id,
                    "country": reg.country_code,
                    "impact": impact,
                    "category": category,
                    "summary": summary
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
