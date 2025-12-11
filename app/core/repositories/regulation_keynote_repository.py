"""
module: regulation_keynote_repository.py
description: RegulationChangeKeynote 테이블 Repository (변경 감지 이력 관리)
author: AI Agent
created: 2025-01-21
updated: 2025-01-22 (헤더 업데이트)
dependencies:
    - sqlalchemy.ext.asyncio
    - app.core.models.regulation_model
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.regulation_model import RegulationChangeKeynote
from app.core.repositories.base_repository import BaseRepository


class RegulationKeynoteRepository(BaseRepository[RegulationChangeKeynote]):
    """RegulationChangeKeynote Repository"""
    
    def __init__(self):
        super().__init__(RegulationChangeKeynote)
    
    async def create_keynote(
        self,
        db: AsyncSession,
        keynote_data: dict
    ) -> RegulationChangeKeynote:
        """
        Keynote 생성
        
        Args:
            db: 데이터베이스 세션
            keynote_data: keynote JSON 데이터
        
        Returns:
            생성된 RegulationChangeKeynote 객체
        """
        keynote = RegulationChangeKeynote(keynote_text=keynote_data)
        db.add(keynote)
        await db.flush()
        await db.refresh(keynote)
        return keynote
    
    async def get_all_keynotes(
        self,
        db: AsyncSession,
        country: Optional[str] = None
    ) -> List[RegulationChangeKeynote]:
        """
        모든 keynote 조회 (국가 필터 옵션)
        
        Args:
            db: 데이터베이스 세션
            country: 국가 코드 필터 (옵션)
        
        Returns:
            RegulationChangeKeynote 리스트
        """
        query = select(RegulationChangeKeynote)
        
        # 국가 필터 (JSONB 쿼리)
        if country:
            query = query.where(
                RegulationChangeKeynote.keynote_text['country'].astext == country
            )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def get_keynote_by_id(
        self,
        db: AsyncSession,
        keynote_id: int
    ) -> Optional[RegulationChangeKeynote]:
        """
        ID로 keynote 조회
        
        Args:
            db: 데이터베이스 세션
            keynote_id: keynote ID
        
        Returns:
            RegulationChangeKeynote 또는 None
        """
        result = await db.execute(
            select(RegulationChangeKeynote).where(
                RegulationChangeKeynote.keynote_id == keynote_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_recent_changes(
        self,
        db: AsyncSession,
        country: Optional[str] = None,
        limit: int = 10
    ) -> List[RegulationChangeKeynote]:
        """
        최근 변경 이력 조회 (대시보드용)
        
        Args:
            db: 데이터베이스 세션
            country: 국가 코드 필터 (옵션)
            limit: 최대 개수
        
        Returns:
            RegulationChangeKeynote 리스트
        """
        query = select(RegulationChangeKeynote).order_by(
            RegulationChangeKeynote.created_at.desc()
        )
        
        if country:
            query = query.where(
                RegulationChangeKeynote.keynote_text['country'].astext == country
            )
        
        query = query.limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def get_high_impact_changes(
        self,
        db: AsyncSession,
        country: Optional[str] = None
    ) -> List[RegulationChangeKeynote]:
        """
        고영향도 변경 조회 (HIGH confidence 필터)
        
        Args:
            db: 데이터베이스 세션
            country: 국가 코드 필터 (옵션)
        
        Returns:
            RegulationChangeKeynote 리스트
        """
        from sqlalchemy import func
        
        query = select(RegulationChangeKeynote).where(
            func.jsonb_array_length(
                RegulationChangeKeynote.keynote_text['section_changes']
            ) > 0
        )
        
        if country:
            query = query.where(
                RegulationChangeKeynote.keynote_text['country'].astext == country
            )
        
        query = query.order_by(RegulationChangeKeynote.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def create_keynote_with_mapping(
        self,
        db: AsyncSession,
        change_keynote_data: dict,
        mapping_data: dict
    ) -> RegulationChangeKeynote:
        """
        Change Detection + Mapping 통합 Keynote 생성
        
        Args:
            db: 데이터베이스 세션
            change_keynote_data: Change Detection 결과
            mapping_data: Mapping 결과 (제품별 매핑 정보)
        
        Returns:
            생성된 RegulationChangeKeynote 객체
        """
        # Change Detection + Mapping 데이터 병합
        integrated_data = {
            **change_keynote_data,
            "mapping_summary": {
                "total_products": len(mapping_data.get("items", [])),
                "product_mappings": [
                    {
                        "product_name": item.get("product_name"),
                        "feature_name": item.get("feature_name"),
                        "applies": item.get("applies"),
                        "required_value": item.get("required_value")
                    }
                    for item in mapping_data.get("items", [])[:10]  # 최대 10개만
                ]
            }
        }
        
        return await self.create_keynote(db, integrated_data)
