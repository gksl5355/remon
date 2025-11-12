from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from datetime import date
import json
import os

router = APIRouter(prefix="/admin/summary", tags=["Admin - Summary"])

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
                    "국가 / 지역: 미국 (USA)",
                    "규제 카테고리: 라벨 표시 – 니코틴 함량 표기",
                    "변경 요약: FDA 니코틴 경고 문구 강화 (2025년 10월 1일부터 적용)",
                    "영향도: 높음 (High Impact)"
                ]
            },
            "products": {
                "title": "2. 영향받는 제품 목록",
                "type": "table",
                "headers": ["제품명", "브랜드", "조치"],
                "rows": [
                    ["VapeMax Bold 10mg", "FreedomVape", "경고문 추가 필요"],
                    ["PureAir 8mg", "NicFree Inc.", "라벨 수정 필요"]
                ]
            },
            "changes": {
                "title": "3. 주요 변경 사항 해석",
                "type": "list",
                "content": [
                    "청소년 노출 최소화 목적의 경고문 강화",
                    "니코틴 제품 광고 문구 규제 강화",
                    "수입 제품 표기 검수 절차 추가"
                ]
            },
            "strategy": {
                "title": "4. 대응 전략 제안",
                "type": "paragraph",
                "content": [
                    "1차 대응: FDA 가이드라인 검토 및 라벨 갱신",
                    "2차 대응: 광고물 전면 수정 및 법무팀 협의",
                    "3차 대응: 리스크 보고서 제출"
                ]
            },
            "references": {
                "title": "5. 참고 및 원문 링크",
                "type": "links",
                "content": [
                    {
                        "text": "FDA Tobacco Regulatory Plan (2025)",
                        "url": "https://www.fda.gov/tobacco-products"
                    }
                ]
            }
        }
    },
}

# 모든 요약 리포트 목록
@router.get("")
async def list_summary():
    return REPORTS


# 특정 리포트 상세 조회
@router.get("/{report_id}")
async def get_summary(report_id: int):
    if report_id not in REPORTS:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    return REPORTS[report_id]


# 특정 리포트 수정 (sections 업데이트)
@router.put("/{report_id}")
async def update_summary(report_id: int, body: dict):
    if report_id not in REPORTS:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
    REPORTS[report_id]["sections"] = body.get("sections", REPORTS[report_id]["sections"])
    REPORTS[report_id]["last_updated"] = str(date.today())
    return {"message": "리포트가 수정되었습니다.", "report": REPORTS[report_id]}


# DELETE: 리포트 삭제
@router.delete("/{report_id}")
async def delete_summary(report_id: int):
    if report_id not in REPORTS:
        raise HTTPException(status_code=404, detail="삭제할 리포트가 없습니다.")
    REPORTS.pop(report_id)
    return {"message": "삭제 완료"}


# PDF 다운로드 (임시 더미 파일)
@router.get("/{report_id}/download/pdf")
async def download_pdf(report_id: int):
    dummy_pdf_path = "sample_report.pdf"

    # 더미 PDF 파일 없으면 생성
    if not os.path.exists(dummy_pdf_path):
        with open(dummy_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n% Dummy PDF for demo\n")

    return FileResponse(
        path=dummy_pdf_path,
        filename=f"report_{report_id}.pdf",
        media_type="application/pdf"
    )
