from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any

from app.core.models.intermediate_model import IntermediateOutput
from app.core.schemas.intermediate_schema import IntermediateOutputCreate

class IntermediateRepository:
    
    async def create_intermediate_output(
        self, 
        db: AsyncSession, 
        intermediate_data: IntermediateOutputCreate
    ) -> IntermediateOutput:
        """
        중간 산출물 데이터 저장
        """
        # Pydantic 모델 -> DB 모델 변환
        db_obj = IntermediateOutput(
            regulation_id=intermediate_data.regulation_id,
            intermediate_data=intermediate_data.intermediate_data
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_regulation_id(
        self, 
        db: AsyncSession, 
        regulation_id: int
    ) -> List[IntermediateOutput]:
        """
        특정 규제 ID에 연결된 모든 중간 산출물 조회
        """
        query = select(IntermediateOutput).where(IntermediateOutput.regulation_id == regulation_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_id(
        self, 
        db: AsyncSession, 
        intermediate_id: int
    ) -> Optional[IntermediateOutput]:
        """
        ID로 단건 조회
        """
        query = select(IntermediateOutput).where(IntermediateOutput.intermediate_id == intermediate_id)
        result = await db.execute(query)
        return result.scalars().first()