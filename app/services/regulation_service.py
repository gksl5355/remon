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

from app.config.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository

# logger = logging.getLogger(__name__)


class RegulationService:
    """규제 문서 관련 비즈니스 로직을 처리하는 서비스 클래스"""

    def __init__(self):
        self.repo = RegulationKeynoteRepository()

    async def get_regulations(self, db: AsyncSession) -> dict:
        """
        규제 문서 목록을 조회한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.

        Returns:
            dict: 규제 문서 목록 (프론트 형식).
        """
        
        # risk_level 한글 변환 맵
        RISK_LEVEL_MAP = {
            "Low": "낮음",
            "Medium": "보통",
            "High": "높음"
        }
        
        try:
            # keynote와 impact_score를 포함하여 조회
            regulations = await self.repo.get_all_keynotes(db)
            result = []
            for keynote in regulations:
                # keynote_text는 ["country: US", "category: demo", ...] 형태
                keynote_data = {}
                for item in keynote.keynote_text:
                    if ": " in item:
                        key, value = item.split(": ", 1)
                        keynote_data[key] = value
                
                # 프론트 형식으로 변환
                result.append({
                    "id": keynote.keynote_id,
                    "country": keynote_data.get("country", ""),
                    "category": keynote_data.get("category", ""),
                    "summary": keynote_data.get("summary", ""),
                    "impact": RISK_LEVEL_MAP.get(keynote_data.get("impact", ""), keynote_data.get("impact", ""))
                })
            
            logger.info(f"Found {len(result)} regulations")
            return {
                "today_count": len(result),
                "regulations": result #db에서 가져온 json 구조?
            }
            
        except Exception as e:
            logger.error(f"Error fetching regulations: {e}", exc_info=True)
            # 에러 발생해도 빈 배열 반환
            return {
                "today_count": 0,
                "regulations": []
            }
