from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Regulations"])

# 규제 목록
REGULATIONS = [
    {"id": 1, "impact": "높음", "country": "EU", "category": "라벨 표시", "summary": "니코틴 함량 표기 기준 강화 (EU Directive 2025/127)"},
    {"id": 2, "impact": "보통", "country": "US", "category": "광고 규제", "summary": "전자담배 광고 규제 완화 및 청소년 보호 가이드라인 개정"},
    {"id": 3, "impact": "긴급", "country": "US", "category": "광고 규제", "summary": "전자담배 광고 규제 완화 및 청소년 보호 가이드라인 개정"},
]

@router.get("/regulations")
def get_regulations():
    return {"today_count": len(REGULATIONS), "regulations": REGULATIONS}

@router.get("/regulations/{regulation_id}")
def get_regulation(regulation_id: int):
    reg = next((r for r in REGULATIONS if r["id"] == regulation_id), None)
    if not reg:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return reg
