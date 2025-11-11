# app/api/report_api.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["Reports"])

# 예시 데이터
REPORTS = {
    1: {
        "title": "EU 니코틴 라벨 표기 강화 리포트",
        "last_updated": "2025-11-11",
        "sections": {
            "summary": {
                "title": "1. 규제 변경 요약",
                "type": "paragraph",
                "content": [
                    "국가 / 지역: 유럽연합 (EU)",
                    "규제 카테고리: 라벨 표시 – 니코틴 함량 표기",
                    "변경 요약: 니코틴 함량 표기 기준 강화 (2025년 12월 1일부터 0.01mg 단위 표기 의무화)",
                    "영향도: 높음 (High Impact)"
                ]
            },
            "products": {
                "title": "2. 영향받는 제품 목록",
                "type": "table",
                "headers": ["제품명", "브랜드", "조치"],
                "rows": [
                    ["VapeX Mint 20mg", "SmokeFree Co.", "라벨 수정 필요"],
                    ["CloudHit Berry 15mg", "PureVapor", "라벨 수정 필요"]
                ]
            },
            "changes": {
                "title": "3. 주요 변경 사항 해석",
                "type": "list",
                "content": [
                    "EU 내 니코틴 제품 표준화로 라벨 디자인 전면 수정 필요",
                    "측정 오차 미표시는 불법 유통 간주 가능성",
                    "온라인몰 및 광고 매체에도 동일 표기 규정 적용"
                ]
            },
            "strategy": {
                "title": "4. 대응 전략 제안",
                "type": "paragraph",
                "content": [
                    "1차 대응: 라벨 수정 및 시험 재실시 (R&D팀)",
                    "2차 대응: 패키지 수정 및 재고 소진 계획 (디자인팀)",
                    "3차 대응: 온라인몰 설명 업데이트 (마케팅팀)"
                ]
            },
            "references": {
                "title": "5. 참고 및 원문 링크",
                "type": "links",
                "content": [
                    {
                        "text": "Directive 2014/40/EU – Tobacco Products Directive (TPD)",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32014L0040"
                    },
                    {
                        "text": "EU Official Journal L127/1 – Amendments on Nicotine Labeling",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL%3A2025%3A127%3ATOC"
                    }
                ]
            }
        }
    },
    2: {
        "title": "USA 니코틴 라벨 표기 강화 리포트",
        "last_updated": "2025-11-11",
        "sections": {
            "summary": {
                "title": "1. 규제 변경 요약",
                "type": "paragraph",
                "content": [
                    "국가 / 지역: 유럽연합 (EU)",
                    "규제 카테고리: 라벨 표시 – 니코틴 함량 표기",
                    "변경 요약: 니코틴 함량 표기 기준 강화 (2025년 12월 1일부터 0.01mg 단위 표기 의무화)",
                    "영향도: 높음 (High Impact)"
                ]
            },
            "products": {
                "title": "2. 영향받는 제품 목록",
                "type": "table",
                "headers": ["제품명", "브랜드", "조치"],
                "rows": [
                    ["VapeX Mint 20mg", "SmokeFree Co.", "라벨 수정 필요"],
                    ["CloudHit Berry 15mg", "PureVapor", "라벨 수정 필요"]
                ]
            },
            "changes": {
                "title": "3. 주요 변경 사항 해석",
                "type": "list",
                "content": [
                    "EU 내 니코틴 제품 표준화로 라벨 디자인 전면 수정 필요",
                    "측정 오차 미표시는 불법 유통 간주 가능성",
                    "온라인몰 및 광고 매체에도 동일 표기 규정 적용"
                ]
            },
            "strategy": {
                "title": "4. 대응 전략 제안",
                "type": "paragraph",
                "content": [
                    "1차 대응: 라벨 수정 및 시험 재실시 (R&D팀)",
                    "2차 대응: 패키지 수정 및 재고 소진 계획 (디자인팀)",
                    "3차 대응: 온라인몰 설명 업데이트 (마케팅팀)"
                ]
            },
            "references": {
                "title": "5. 참고 및 원문 링크",
                "type": "links",
                "content": [
                    {
                        "text": "Directive 2014/40/EU – Tobacco Products Directive (TPD)",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32014L0040"
                    },
                    {
                        "text": "EU Official Journal L127/1 – Amendments on Nicotine Labeling",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL%3A2025%3A127%3ATOC"
                    }
                ]
            }
        }
    },
    3: {
        "title": "미국 니코틴 라벨 표기 강화 리포트",
        "last_updated": "2025-11-11",
        "sections": {
            "summary": {
                "title": "1. 규제 변경 요약",
                "type": "paragraph",
                "content": [
                    "국가 / 지역: 유럽연합 (EU)",
                    "규제 카테고리: 라벨 표시 – 니코틴 함량 표기",
                    "변경 요약: 니코틴 함량 표기 기준 강화 (2025년 12월 1일부터 0.01mg 단위 표기 의무화)",
                    "영향도: 높음 (High Impact)"
                ]
            },
            "products": {
                "title": "2. 영향받는 제품 목록",
                "type": "table",
                "headers": ["제품명", "브랜드", "조치"],
                "rows": [
                    ["VapeX Mint 20mg", "SmokeFree Co.", "라벨 수정 필요"],
                    ["CloudHit Berry 15mg", "PureVapor", "라벨 수정 필요"]
                ]
            },
            "changes": {
                "title": "3. 주요 변경 사항 해석",
                "type": "list",
                "content": [
                    "EU 내 니코틴 제품 표준화로 라벨 디자인 전면 수정 필요",
                    "측정 오차 미표시는 불법 유통 간주 가능성",
                    "온라인몰 및 광고 매체에도 동일 표기 규정 적용"
                ]
            },
            "strategy": {
                "title": "4. 대응 전략 제안",
                "type": "paragraph",
                "content": [
                    "1차 대응: 라벨 수정 및 시험 재실시 (R&D팀)",
                    "2차 대응: 패키지 수정 및 재고 소진 계획 (디자인팀)",
                    "3차 대응: 온라인몰 설명 업데이트 (마케팅팀)"
                ]
            },
            "references": {
                "title": "5. 참고 및 원문 링크",
                "type": "links",
                "content": [
                    {
                        "text": "Directive 2014/40/EU – Tobacco Products Directive (TPD)",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32014L0040"
                    },
                    {
                        "text": "EU Official Journal L127/1 – Amendments on Nicotine Labeling",
                        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ%3AL%3A2025%3A127%3ATOC"
                    }
                ]
            }
        }
    }
}

# 기간별 종합 리포트 다운로드
@router.get("/reports/combined/download")
async def download_combined_report(
    start_date: str,
    end_date: str
):
    print(f"✅ 요청된 기간: {start_date} ~ {end_date}")

    return JSONResponse({
        "status": "ok",
        "message": "요청 정상 수신",
        "requested_period": f"{start_date} ~ {end_date}",
    })

# 규제별 요약 리포트 조회
@router.get("/reports/{regulation_id}")
def get_report(regulation_id: int):
    report = REPORTS.get(regulation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "regulation_id": regulation_id,
        "title": report["title"],
        "last_updated": report["last_updated"],
        "sections": report["sections"],
    }


# 리포트 다운로드 (PDF)
@router.get("/reports/{regulation_id}/download")
def download_report(regulation_id: int):
    if regulation_id not in REPORTS:
        raise HTTPException(status_code=404, detail="Report not found")

    dummy_path = f"report_{regulation_id}.pdf"
    with open(dummy_path, "wb") as f:
        f.write(b"%PDF-1.4\n% Demo report PDF content\n")

    return FileResponse(dummy_path, media_type="application/pdf", filename=f"{REPORTS[regulation_id]['title']}.pdf")
