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

from typing import Optional
from app.config.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository

# logger = logging.getLogger(__name__)


class RegulationService:
    """규제 문서 관련 비즈니스 로직을 처리하는 서비스 클래스"""

    def __init__(self):
        self.repo = RegulationKeynoteRepository()

    def _normalize_keynote_text(self, keynote_text):
        """DB에 저장된 keynote_text를 dict 형태로 변환한다."""
        if isinstance(keynote_text, dict):
            return keynote_text

        if isinstance(keynote_text, list):
            converted = {}
            for item in keynote_text:
                if isinstance(item, str) and ": " in item:
                    key, value = item.split(": ", 1)
                    converted[key] = value
            return converted

        return {}

    def _map_confidence_to_level(self, confidence_value):
        """신뢰도 문자열을 정수 레벨로 변환한다."""
        if not confidence_value:
            return 1
        mapping = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        return mapping.get(str(confidence_value).upper(), 1)

    def _infer_impact_from_section_changes(self, section_changes):
        """섹션 변경 정보에서 최대 영향도를 추정한다."""
        if not isinstance(section_changes, list):
            return 1

        levels = []
        for section in section_changes:
            if not isinstance(section, dict):
                continue
            levels.append(self._map_confidence_to_level(section.get("confidence_level")))

            numerical_changes = section.get("numerical_changes") or []
            for num_change in numerical_changes:
                impact = num_change.get("impact")
                if impact:
                    levels.append(self._map_confidence_to_level(impact))

        return max(levels) if levels else 1

    def _format_collection_time(self, generated_at, analysis_date):
        """수집 시간을 프론트가 바로 쓸 수 있는 문자열로 변환한다."""
        if generated_at:
            try:
                return generated_at.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        if analysis_date:
            return str(analysis_date)
        return ""

    def _build_articles(self, section_changes):
        """section_changes 리스트를 프론트에서 사용하는 기사 리스트 형태로 변환한다."""
        articles = []
        if not isinstance(section_changes, list):
            return articles

        for idx, section in enumerate(section_changes, start=1):
            if not isinstance(section, dict):
                continue

            change_type = section.get("change_type")
            if (change_type == "removed"):
                change_type = "삭제"
            elif (change_type == "new_clause"):
                change_type = "조항 신설"
            elif (change_type == "wording_only"):
                change_type = "문언 정비"
            elif (change_type == "scope_change"):
                change_type = "범위 변경"
            elif (change_type == "" or change_type is None):
                change_type = "개정 없음"




            review_level = self._map_confidence_to_level(section.get("confidence_level"))
            for num_change in section.get("numerical_changes") or []:
                review_level = max(
                    review_level,
                    self._map_confidence_to_level(num_change.get("impact")),
                )

            articles.append(
                {
                    "id": idx,
                    "title": section.get("section_ref"),
                    "summary": change_type,
                    "reviewLevel": review_level,
                    "hasChange": bool(section.get("change_detected", False)),
                }
            )

        return articles

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
            "LOW": "낮음",
            "MEDIUM": "보통",
            "HIGH": "높음"
        }
        
        try:
            # keynote와 impact_score를 포함하여 조회
            regulations = await self.repo.get_all_keynotes(db)
            result = []
            for keynote in regulations:
                keynote_data = self._normalize_keynote_text(keynote.keynote_text)
                impact_raw = keynote_data.get("impact", "")
                impact_upper = impact_raw.upper() if isinstance(impact_raw, str) else ""
                
                # 프론트 형식으로 변환
                result.append({
                    "id": keynote.keynote_id,
                    "country": keynote_data.get("country", ""),
                    "category": keynote_data.get("category", ""),
                    "summary": keynote_data.get("summary", ""),
                    "impact": RISK_LEVEL_MAP.get(impact_upper, impact_raw)
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
    
    async def get_regulations_by_country(self, db: AsyncSession, country: str) -> dict:
        """
        국가별 규제 목록 조회
        
        Args:
            db: 데이터베이스 세션
            country: 국가 코드 (US, ID, RU)
            
        Returns:
            dict: {"collectedTime": str, "files": list}
        """
        try:
            keynotes = await self.repo.get_recent_changes(db, country)
            
            if not keynotes:
                return {"collectedTime": "", "files": []}
            
            # impact 문자열을 숫자로 변환
            impact_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
            
            files = []
            for k in keynotes:
                keynote_data = self._normalize_keynote_text(k.keynote_text)
                impact_raw = keynote_data.get("impact")
                impact_level = impact_map.get(
                    impact_raw.upper() if isinstance(impact_raw, str) else "",
                    None
                )
                if impact_level is None:
                    impact_level = self._infer_impact_from_section_changes(
                        keynote_data.get("section_changes")
                    )

                files.append(
                    {
                        "id": k.keynote_id,
                        "title": keynote_data.get("title", ""),
                        "impactLevel": impact_level or 1,
                        "category": keynote_data.get("analysis_date", "")
                    }
                )
            
            # 최신 generated_at 사용
            collected_time = keynotes[0].generated_at.strftime("%Y-%m-%d %H:%M:%S") if keynotes else ""
            
            logger.info(f"Found {len(files)} regulations for country={country}")
            return {
                "collectedTime": collected_time,
                "files": files
            }
            
        except Exception as e:
            logger.error(f"Error fetching regulations by country: {e}", exc_info=True)
            return {"collectedTime": "", "files": []}

    async def get_regulation_detail(
        self,
        db: AsyncSession,
        regulation_id: int,
        country: Optional[str] = None
    ) -> Optional[dict]:
        """
        규제 문서 상세 정보를 조회한다. (DB -> 프론트 포맷 변환)

        Args:
            db: 데이터베이스 세션
            regulation_id: regulation_change_keynotes.keynote_id 값
            country: 국가 코드 (옵션, 일치 여부만 확인)

        Returns:
            dict | None: 프론트에서 사용하는 상세 데이터
        """
        try:
            keynote = await self.repo.get_keynote_by_id(db, regulation_id)
            if not keynote:
                return None

            keynote_data = self._normalize_keynote_text(keynote.keynote_text)

            if country:
                stored_country = (keynote_data.get("country") or "").lower()
                if stored_country and stored_country != country.lower():
                    logger.warning(
                        "Country mismatch for regulation_id=%s (expected=%s, stored=%s)",
                        regulation_id,
                        country,
                        stored_country,
                    )

            articles = self._build_articles(keynote_data.get("section_changes"))
            impact_level = self._infer_impact_from_section_changes(
                keynote_data.get("section_changes")
            )
            if articles:
                impact_level = max(impact_level, max(a["reviewLevel"] for a in articles))

            collected_time = self._format_collection_time(
                getattr(keynote, "generated_at", None),
                keynote_data.get("analysis_date"),
            )

            document_info = {
                "promulgationDate": keynote_data.get("promulgation_date") or keynote_data.get("promulgationDate") or "",
                "effectiveDate": keynote_data.get("effective_date") or keynote_data.get("effectiveDate") or "",
                "collectionTime": collected_time,
                "collectedTime": collected_time,  # 프론트 타이포 호환
            }

            return {
                "id": keynote.keynote_id,
                "fileName": keynote_data.get("citation_code") or keynote_data.get("title") or f"regulation_{keynote.keynote_id}",
                "title": keynote_data.get("title", ""),
                "impactLevel": impact_level or 1,
                "documentInfo": document_info,
                "articles": articles,
                "aiReports": keynote_data.get("change_summary") or {},
                "cocollected_time": collected_time,
            }
        except Exception as e:
            logger.error(f"Error fetching regulation detail: {e}", exc_info=True)
            return None
