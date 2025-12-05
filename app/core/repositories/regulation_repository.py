"""
현재 안쓰는 코드
"""

# from typing import List, Optional
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from sqlalchemy.orm import selectinload
# from core.models import Regulation, RegulationVersion, RegulationTranslation
# from .base_repository import BaseRepository

# class RegulationRepository(BaseRepository[Regulation]):
#     def __init__(self):
#         super().__init__(Regulation)
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationTranslation
from .base_repository import BaseRepository

class RegulationRepository(BaseRepository[Regulation]):
    """규제 Repository"""
    
    def __init__(self):
        super().__init__(Regulation)


    async def get_by_country(
        self, db: AsyncSession, country_code: str
    ) -> List[Regulation]:
        """특정 국가의 모든 규제 조회 (JSONB 쿼리)"""
        from sqlalchemy import text
        result = await db.execute(
            text("""
                SELECT regulation_id, regul_data, citation_code, created_at
                FROM regulations 
                WHERE regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' = :country
                ORDER BY created_at DESC
            """),
            {"country": country_code}
        )
        regulations = []
        for row in result.fetchall():
            reg = Regulation()
            reg.regulation_id = row[0]
            reg.regul_data = row[1]
            reg.citation_code = row[2]
            reg.created_at = row[3]
            regulations.append(reg)
        return regulations
    
    async def get_with_versions_by_country(
        self, db: AsyncSession, country_code: str = None
    ) -> List[Regulation]:
        """버전 정보를 포함한 규제 조회 (JSONB 쿼리)"""
        from sqlalchemy import text
        
        if country_code:
            sql = """
                SELECT regulation_id, regul_data, citation_code, created_at
                FROM regulations 
                WHERE regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' = :country
                ORDER BY created_at DESC
            """
            params = {"country": country_code}
        else:
            sql = """
                SELECT regulation_id, regul_data, citation_code, created_at
                FROM regulations 
                ORDER BY created_at DESC
            """
            params = {}
        
        result = await db.execute(text(sql), params)
        regulations = []
        for row in result.fetchall():
            reg = Regulation()
            reg.regulation_id = row[0]
            reg.regul_data = row[1]
            reg.citation_code = row[2]
            reg.created_at = row[3]
            regulations.append(reg)
        return regulations
    
    async def get_with_versions(
        self, db: AsyncSession, regulation_id: int
    ) -> Optional[Regulation]:
        """버전 정보를 포함한 규제 조회"""
        result = await db.execute(
            select(Regulation)
            .options(selectinload(Regulation.versions))
            .where(Regulation.regulation_id == regulation_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_country_and_date_range(
        self, db: AsyncSession, country_code: str, start_date: str = None, end_date: str = None
    ) -> List[Regulation]:
        """국가 및 날짜 범위로 규제 조회 (JSONB 쿼리)"""
        from sqlalchemy import text
        
        sql = """
            SELECT regulation_id, regul_data, citation_code, created_at
            FROM regulations 
            WHERE regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' = :country
        """
        params = {"country": country_code}
        
        if start_date:
            sql += " AND regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'effective_date' >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            sql += " AND regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'effective_date' <= :end_date"
            params["end_date"] = end_date
        
        sql += " ORDER BY created_at DESC"
        
        result = await db.execute(text(sql), params)
        regulations = []
        for row in result.fetchall():
            reg = Regulation()
            reg.regulation_id = row[0]
            reg.regul_data = row[1]
            reg.citation_code = row[2]
            reg.created_at = row[3]
            regulations.append(reg)
        return regulations
    
    async def find_by_title_and_country(
        self, 
        db: AsyncSession, 
        title: str, 
        country_code: str,
        exclude_regulation_id: int = None
    ) -> Optional[Regulation]:
        """제목과 국가로 Legacy 규제 검색 (JSONB)"""
        from sqlalchemy import text
        
        if exclude_regulation_id:
            sql = """
                SELECT regulation_id, regul_data 
                FROM regulations 
                WHERE regul_data->>'title' ILIKE :title
                AND regul_data->>'jurisdiction_code' = :country
                AND regulation_id != :exclude_id
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = {"title": f"%{title}%", "country": country_code, "exclude_id": exclude_regulation_id}
        else:
            sql = """
                SELECT regulation_id, regul_data 
                FROM regulations 
                WHERE regul_data->>'title' ILIKE :title
                AND regul_data->>'jurisdiction_code' = :country
                ORDER BY created_at DESC
                LIMIT 1
            """
            params = {"title": f"%{title}%", "country": country_code}
        
        result = await db.execute(text(sql), params)
        row = result.fetchone()
        if row:
            reg = Regulation()
            reg.regulation_id = row[0]
            reg.regul_data = row[1]
            return reg
        return None
    
    async def get_regul_data(
        self, 
        db: AsyncSession, 
        regulation_id: int
    ) -> Optional[Dict]:
        """regulation_id로 regul_data (vision 결과) 조회"""
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT regul_data FROM regulations WHERE regulation_id = :reg_id"),
            {"reg_id": regulation_id}
        )
        row = result.fetchone()
        return row[0] if row else None
    
    async def create_from_vision_result(
        self,
        db: AsyncSession,
        vision_result: Dict
    ) -> Regulation:
        """Vision Pipeline 결과를 DB에 저장"""
        # 첫 페이지 메타데이터 추출
        vision_pages = vision_result.get("vision_extraction_result", [])
        if not vision_pages:
            raise ValueError("vision_extraction_result가 비어있습니다")
        
        first_page = vision_pages[0]
        metadata = first_page.get("structure", {}).get("metadata", {})
        
        # citation_code 추출 (변경 감지용)
        citation_code = metadata.get("citation_code")
        
        # Regulation 생성
        regulation = Regulation(
            citation_code=citation_code,
            regul_data=vision_result  # 전체 Vision 결과 저장
        )
        
        db.add(regulation)
        await db.flush()
        await db.refresh(regulation)
        
        return regulation
    
    async def find_by_citation_code(
        self,
        db: AsyncSession,
        citation_code: str,
        exclude_regulation_id: Optional[int] = None
    ) -> Optional[Regulation]:
        """citation_code로 규제 검색 (변경 감지 대상 찾기)"""
        query = select(Regulation).where(Regulation.citation_code == citation_code)
        
        if exclude_regulation_id:
            query = query.where(Regulation.regulation_id != exclude_regulation_id)
        
        query = query.order_by(Regulation.created_at.desc()).limit(1)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    

    # 추가
    async def get_regulations_count_by_country(
        self,
        db: AsyncSession
    ) -> Dict[str, int]:
        """
        국가별 규제 수 집계 (JSONB 쿼리)
        
        Returns:
            {"US": 10, "KR": 5, ...}
        """
        from sqlalchemy import text
        
        result = await db.execute(
            text("""
                SELECT 
                    regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' as country,
                    COUNT(*) as count
                FROM regulations
                WHERE regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' IS NOT NULL
                GROUP BY country
                ORDER BY count DESC
            """)
        )
        
        return {row[0]: row[1] for row in result.fetchall()}
# 여기까지


class RegulationVersionRepository(BaseRepository[RegulationVersion]):
    def __init__(self):
        super().__init__(RegulationVersion)
    
    async def get_latest_version(
        self, db: AsyncSession, regulation_id: int
    ) -> Optional[RegulationVersion]:
        """가장 최신 버전 조회"""
        result = await db.execute(
            select(RegulationVersion)
            .where(RegulationVersion.regulation_id == regulation_id)
            .order_by(RegulationVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

class RegulationTranslationRepository(BaseRepository[RegulationTranslation]):
    def __init__(self):
        super().__init__(RegulationTranslation)
    
    async def get_by_language(
        self, db: AsyncSession, version_id: int, language_code: str
    ) -> Optional[RegulationTranslation]:
        """특정 언어의 번역 조회"""
        result = await db.execute(
            select(RegulationTranslation).where(
                RegulationTranslation.regulation_version_id == version_id,
                RegulationTranslation.language_code == language_code
            )
        )
        return result.scalar_one_or_none()

 # 기존 메서드들...
    
    async def get_all_with_details(
        self, 
        db: AsyncSession
    ) -> List[Regulation]:
        """
        모든 규제 정보를 상세 정보와 함께 조회
        (Admin - List Regulations용)
        """
        result = await db.execute(
            select(Regulation)
            .options(selectinload(Regulation.version))
            .order_by(Regulation.created_at.desc())
        )
        return list(result.unique().scalars().all())
    
    async def get_multi_with_filters(
        self,
        db: AsyncSession,
        country_code: Optional[str] = None,
        authority: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Regulation]:
        """
        필터링된 규제 목록 조회 (JSONB 쿼리)
        """
        from sqlalchemy import text
        
        sql = "SELECT regulation_id, regul_data, citation_code, created_at FROM regulations WHERE 1=1"
        params = {}
        
        if country_code:
            sql += " AND regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'jurisdiction_code' = :country"
            params["country"] = country_code
        
        if authority:
            sql += " AND regul_data->'vision_extraction_result'->0->'structure'->'metadata'->>'authority' ILIKE :authority"
            params["authority"] = f"%{authority}%"
        
        sql += " ORDER BY created_at DESC OFFSET :skip LIMIT :limit"
        params.update({"skip": skip, "limit": limit})
        
        result = await db.execute(text(sql), params)
        regulations = []
        for row in result.fetchall():
            reg = Regulation()
            reg.regulation_id = row[0]
            reg.regul_data = row[1]
            reg.citation_code = row[2]
            reg.created_at = row[3]
            regulations.append(reg)
        return regulations

class RegulationVersionRepository(BaseRepository[RegulationVersion]):
    """규제 버전 Repository"""
    
    def __init__(self):
        super().__init__(RegulationVersion)
    
    async def create_version(
        self,
        db: AsyncSession,
        regulation_id: int,
        **kwargs
    ) -> RegulationVersion:
        """
        새 규제 버전 생성
        """
        # 기술적 검증
        if regulation_id is None:
            raise ValueError("regulation_id cannot be None")
        
        # 자동으로 다음 버전 번호 계산
        latest = await self.get_latest_version(db, regulation_id)
        next_version = (latest.version_number + 1) if latest else 1
        
        version_data = {
            "regulation_id": regulation_id,
            "version_number": next_version,
            **kwargs
        }
        
        return await self.create(db, **version_data)
    
    async def get_latest_version(
        self,
        db: AsyncSession,
        regulation_id: int
    ) -> Optional[RegulationVersion]:
        """가장 최신 버전 조회"""
        result = await db.execute(
            select(RegulationVersion)
            .where(RegulationVersion.regulation_id == regulation_id)
            .order_by(RegulationVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()