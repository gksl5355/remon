from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from datetime import date

router = APIRouter(prefix="/admin/websearch", tags=["Admin - WebSearch"])

# Pydantic 모델 정의
class WebSearchItem(BaseModel):
    title: str
    country: str
    url: HttpUrl


# 예시 데이터 (임시 메모리)
websearch_data = [
    {
        "id": 1,
        "title": "EU 포장재 규제 가이드",
        "country": "EU",
        "date": "2025-11-09",
        "url": "https://europa.eu/regulation",
    },
    {
        "id": 2,
        "title": "KR 식약처 공지사항",
        "country": "KR",
        "date": "2025-11-08",
        "url": "https://mfds.go.kr",
    },
]


# 전체 목록 조회
@router.get("")
async def list_websearch():
    """웹서치 데이터 전체 목록 반환"""
    return websearch_data


# 새 항목 추가
@router.post("")
async def add_websearch(item: WebSearchItem):
    """새 웹서치 항목 등록"""
    new_item = {
        "id": len(websearch_data) + 1,
        "title": item.title,
        "country": item.country,
        "date": str(date.today()),
        "url": str(item.url),
    }
    websearch_data.append(new_item)
    return {"message": "등록 성공", "item": new_item}


# 항목 삭제
@router.delete("/{item_id}")
async def delete_websearch(item_id: int):
    """특정 항목 삭제"""
    global websearch_data
    before_count = len(websearch_data)
    websearch_data = [i for i in websearch_data if i["id"] != item_id]

    if len(websearch_data) == before_count:
        raise HTTPException(status_code=404, detail="삭제할 항목을 찾을 수 없습니다.")

    return {"message": f"{item_id}번 데이터 삭제 완료"}
