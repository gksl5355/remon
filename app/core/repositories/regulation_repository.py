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
        """특정 국가의 모든 규제 조회"""
        result = await db.execute(
            select(Regulation).where(Regulation.country_code == country_code)
        )
        return result.scalars().all()
    
    async def get_with_keynotes_and_impact(
        self, db: AsyncSession, country_code: str = None
    ) -> List[Regulation]:
        """keynote와 impact_score를 포함한 규제 조회"""
        from app.core.models.regulation_model import RegulationVersion, RegulationChangeKeynote
        from app.core.models.impact_model import ImpactScore
        
        query = select(Regulation).options(
            selectinload(Regulation.versions)
            .selectinload(RegulationVersion.keynotes)
            .selectinload(RegulationChangeKeynote.impact_score)
        )
        
        if country_code:
            query = query.where(Regulation.country_code == country_code)
        
        result = await db.execute(query)
        return result.scalars().all()
    
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
    
    async def get_active_regulations(
        self, db: AsyncSession, country_code: str
    ) -> List[Regulation]:
        """활성 상태의 규제만 조회"""
        result = await db.execute(
            select(Regulation)
            .where(
                Regulation.country_code == country_code,
                Regulation.status == "active"
            )
        )
        return result.scalars().all()
    

    # 추가
    async def check_all_products_processed(
        self,
        db: AsyncSession
    ) -> Dict[str, bool]:
        """
        모든 제품에 대한 처리 상태 확인
        (ValidationAgent용 - State 체크포인트)
        
        Returns:
            {"all_processed": True/False, "pending_count": int}
        """
        # 예: 모든 제품에 대해 최신 규제 번역이 있는지 확인
        # 실제 로직은 비즈니스 요구사항에 따라 다름
        
        from sqlalchemy import func, select
        from core.models.product_model import Product
        from core.models.regulation_model import RegulationTranslation
        
        # 전체 제품 수
        total_products = await db.execute(select(func.count(Product.product_id)))
        total = total_products.scalar()
        
        # 처리된 제품 수 (예시 로직)
        # 실제로는 더 복잡한 조건일 수 있음
        processed = 0  # TODO: 실제 쿼리 구현
        
        return {
            "all_processed": total == processed,
            "total_count": total,
            "processed_count": processed,
            "pending_count": total - processed
        }
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
            .options(
                selectinload(Regulation.versions),
                joinedload(Regulation.country),
                joinedload(Regulation.data_source)
            )
            .order_by(Regulation.created_at.desc())
        )
        return list(result.unique().scalars().all())
    
    async def get_multi_with_filters(
        self,
        db: AsyncSession,
        country_code: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Regulation]:
        """
        필터링된 규제 목록 조회
        """
        query = select(Regulation)
        
        if country_code:
            query = query.where(Regulation.country_code == country_code)
        if status:
            query = query.where(Regulation.status == status)
        
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())

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