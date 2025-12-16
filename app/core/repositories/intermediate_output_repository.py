"""
module: intermediate_output_repository.py
description: 중간 결과물 저장/조회 Repository (HITL 강화용)
author: AI Agent
created: 2025-01-21
updated: 2025-01-21
dependencies:
    - sqlalchemy
    - app.core.models.intermediate_output_model
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class IntermediateOutputRepository:
    """중간 결과물 Repository"""

    async def save_intermediate(
        self,
        db: AsyncSession,
        regulation_id: int,
        node_name: str,
        data: Dict[str, Any]
    ) -> int:
        """
        중간 결과물 저장 (중복 방지: regulation_id + node_name 기준)
        
        Args:
            db: DB 세션
            regulation_id: 규제 ID
            node_name: 노드 이름 (change_detection, map_products)
            data: 저장할 데이터 (JSONB)
        
        Returns:
            intermediate_id: 저장된 ID
        """
        import json
        
        # 기존 데이터 확인 (중복 방지)
        result = await db.execute(
            text("""
                SELECT intermediate_id, intermediate_data 
                FROM intermediate_output 
                WHERE regulation_id = :reg_id
            """),
            {"reg_id": regulation_id}
        )
        row = result.fetchone()
        
        if row:
            # 기존 데이터에 노드별 결과 병합
            intermediate_id = row[0]
            existing_data = row[1] or {}
            existing_data[node_name] = data
            
            await db.execute(
                text("""
                    UPDATE intermediate_output 
                    SET intermediate_data = CAST(:data AS jsonb)
                    WHERE intermediate_id = :id
                """),
                {
                    "data": json.dumps(existing_data, ensure_ascii=False),
                    "id": intermediate_id
                }
            )
            logger.info(f"✅ 중간 결과물 업데이트: intermediate_id={intermediate_id}, node={node_name}")
        else:
            # 신규 생성
            result = await db.execute(
                text("""
                    INSERT INTO intermediate_output (regulation_id, intermediate_data)
                    VALUES (:reg_id, CAST(:data AS jsonb))
                    RETURNING intermediate_id
                """),
                {
                    "reg_id": regulation_id,
                    "data": json.dumps({node_name: data}, ensure_ascii=False)
                }
            )
            intermediate_id = result.fetchone()[0]
            logger.info(f"✅ 중간 결과물 생성: intermediate_id={intermediate_id}, node={node_name}")
        
        return intermediate_id

    async def get_intermediate(
        self,
        db: AsyncSession,
        regulation_id: int,
        node_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        중간 결과물 조회
        
        Args:
            db: DB 세션
            regulation_id: 규제 ID
            node_name: 노드 이름 (None이면 전체 반환)
        
        Returns:
            중간 결과물 데이터 (JSONB)
        """
        result = await db.execute(
            text("""
                SELECT intermediate_data 
                FROM intermediate_output 
                WHERE regulation_id = :reg_id
            """),
            {"reg_id": regulation_id}
        )
        row = result.fetchone()
        
        if not row:
            return None
        
        data = row[0] or {}
        
        if node_name:
            return data.get(node_name)
        
        return data

    async def delete_intermediate(
        self,
        db: AsyncSession,
        regulation_id: int
    ) -> bool:
        """
        중간 결과물 삭제
        
        Args:
            db: DB 세션
            regulation_id: 규제 ID
        
        Returns:
            삭제 성공 여부
        """
        result = await db.execute(
            text("""
                DELETE FROM intermediate_output 
                WHERE regulation_id = :reg_id
                RETURNING intermediate_id
            """),
            {"reg_id": regulation_id}
        )
        deleted = result.fetchone()
        
        if deleted:
            logger.info(f"✅ 중간 결과물 삭제: regulation_id={regulation_id}")
            return True
        
        return False
