"""
module: dashboard_api.py
description: 국제 규제 모닝터링 서비스 REMONAI의 대시보드를 구성하는 API
author: 조영우
created: 2025-12-11
dependencies:
    - fastapi
    - sqlalchemy.ext.asyncio
    - service.dashboard_service.py
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/main",tags=["Dashboard"])

weeklyData = {
  "US": {
    "dates": ["12/1", "12/2", "12/3", "12/4", "12/5", "12/6", "12/7"],
    "changed": [5, 7, 6, 10, 8, 9, 7],
    "impactLevel": [1, 1, 2, 2, 3, 3, 2],
    "productCount": [2, 3, 2, 4, 3, 5, 4]
  },
  "ID": {
    "dates": ["12/1", "12/2", "12/3", "12/4", "12/5", "12/6", "12/7"],
    "changed": [8, 6, 9, 11, 12, 10, 9],
    "impactLevel": [1, 2, 2, 2, 3, 3, 2],
    "productCount": [3, 2, 3, 5, 4, 4, 3]
  },
  "RU": {
    "dates": ["12/1", "12/2", "12/3", "12/4", "12/5", "12/6", "12/7"],
    "changed": [1, 2, 2, 3, 1, 2, 1],
    "impactLevel": [1, 1, 1, 1, 2, 1, 2],
    "productCount": [1, 1, 1, 2, 1, 1, 1]
  }
}

timeline = [
  {
    "id": 1,
    "date": "US · 2025-12-03",
    "title": "금일 변경사항 없음",
    "type": "no-change",
    "description": "시스템 모니터링 활성"
  },
  {
    "id": 2,
    "date": "US · 2025-12-02",
    "title": "전자담배 광고 규제 업데이트",
    "type": "change",
    "description": "디지털 마케팅 제한에 대한 새로운 연방 지침"
  },
  {
    "id": 3,
    "date": "ID · 2025-12-01",
    "title": "포장 요구사항 신설",
    "type": "new",
    "description": "건강 경고 라벨 크기가 패키지의 90%로 증가"
  },
  {
    "id": 4,
    "date": "ID · 2025-11-30",
    "title": "흡연 구역 규제 확대",
    "type": "change",
    "description": "금연 구역으로 지정된 추가 공공 장소"
  },
  {
    "id": 5,
    "date": "RU · 2025-11-28",
    "title": "정기 모니터링 검사 완료",
    "type": "no-change",
    "description": "규제 변경 사항 없음"
  },
  {
    "id": 6,
    "date": "ID · 2025-12-01",
    "title": "니코틴 함량 제한 강화",
    "type": "new",
    "description": "니코틴의 함량 규제가 기존 1.2mg 에서 0.8mg으로 축소"
  },
  {
    "id": 7,
    "date": "ID · 2025-11-30",
    "title": "흡연 구역 규제 확대",
    "type": "change",
    "description": "금연 구역으로 지정된 추가 공공 장소"
  },
  {
    "id": 8,
    "date": "RU · 2025-11-28",
    "title": "정기 모니터링 검사 완료",
    "type": "no-change",
    "description": "규제 변경 사항 없음"
  }
]

@router.get("/weeklyData")
async def get_weeklyData():
    return weeklyData

@router.get("/timeline")
async def get_timeline():
    return timeline

@router.get("/location")
async def get_location():
    return {"message": "location"}

from openai import AsyncOpenAI
from fastapi.responses import StreamingResponse
client = AsyncOpenAI()

@router.post("/report/summary")
async def summarize_report():
    async def generate():
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "규제사항의 최근 동향을 파악하여 3줄로 요약해주세요."},
                {"role": "user", "content": f"주간 데이터: {weeklyData}\n\n타임라인: {timeline}"}
            ],
            stream=True
        )
        async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
    
    return StreamingResponse(generate(), media_type="text/plain")


