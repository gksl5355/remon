"""
app/ai_pipeline/nodes/keynote.py
Keynote 생성 및 DB 저장 노드 (AI 없음, 단순 저장)
"""

import logging
from typing import Dict, Any
from datetime import datetime

from app.ai_pipeline.state import AppState
from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def build_keynote_data(state: AppState) -> dict:
    """AppState에서 keynote JSON 생성"""
    
    # 데이터 추출
    product_info = state.get("product_info", {})
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    impact_scores = state.get("impact_scores", [])
    
    # impact 변환 (High → 높음)
    impact_level = impact_scores[0].get("impact_level", "Medium") if impact_scores else "Medium"
    impact_map = {"High": "높음", "Medium": "보통", "Low": "낮음"}
    
    # JSON 생성 (id는 DB 저장 후 자동 생성)
    return {
        "country": product_info.get("country", "US"),
        "impact": impact_map.get(impact_level, "보통"),
        "category": mapping_items[0].get("parsed", {}).get("category", "기타") if mapping_items else "기타",
        "summary": mapping_items[0].get("regulation_summary", "") if mapping_items else ""
    }


async def keynote_node(state: AppState) -> Dict[str, Any]:
    """
    Keynote 생성 및 DB 저장 노드
    - AI 없음, 단순 데이터 저장
    - state에서 필요한 정보 추출 후 regulation_change_keynotes 테이블에 저장
    """
    logger.info("Keynote 노드 시작")
    
    # 1. state에서 keynote 데이터 생성
    keynote_data = build_keynote_data(state)
    
    # 2. DB 저장
    async with AsyncSessionLocal() as db_session:
        repo = RegulationKeynoteRepository()
        
        try:
            keynote_record = await repo.create_keynote(db_session, keynote_data)
            await db_session.commit()
            
            keynote_id = keynote_record.keynote_id
            logger.info(f"Keynote 저장 완료: keynote_id={keynote_id}")
            
            # 3. 저장된 ID를 keynote_data에 추가
            keynote_data["id"] = keynote_id
            
            return {
                "keynote_id": keynote_id,
                "keynote_data": keynote_data
            }
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Keynote 저장 실패: {e}")
            return {
                "keynote_id": None,
                "keynote_data": keynote_data
            }


# ================================
# 테스트 코드
# ================================
if __name__ == "__main__":
    import asyncio
    
    dummy_state: AppState = {
        "product_info": {
            "product_id": "VAP-002",
            "country": "EU",
        },
        "mapping": {
            "items": [
                {
                    "regulation_summary": "니코틴 함량은 10mg 이하로 제한됨",
                    "parsed": {
                        "category": "니코틴",
                    }
                }
            ]
        },
        "impact_scores": [
            {
                "impact_level": "High",
                "weighted_score": 4.8,
            }
        ]
    }
    
    async def test():
        result = await keynote_node(dummy_state)
        print("=" * 60)
        print("Keynote 생성 결과:")
        print(result)
        print("=" * 60)
    
    asyncio.run(test())
