import os
from datetime import datetime
from typing import Dict, Any, List
from textwrap import dedent

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.ai_pipeline.state import AppState
from app.core.repositories.report_repository import ReportRepository
from app.core.database import get_db_session

load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# LLM chain: 규제 요약
def get_llm_change_summary_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "아래 점수 및 평가 정보를 토대로, 규제 변경의 정책 배경과 핵심 내용을 3문장 이내로 전문적으로 요약하세요."),
        ("human", "{regulation_text}\n{impact_score_detail}")
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return prompt | llm

# LLM chain: 주요 변경 해석
def get_llm_analysis_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "규제 전문과 각 평가 항목/점수 요약을 참고하여, 기업이 실제로 고려해야 할 핵심 변경 포인트를 bullet point로 작성하세요."),
        ("human", "{regulation_text}\n{impact_score_detail}")
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return prompt | llm

# LLM chain: 대응 전략
def get_llm_strategy_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "규제 내용과 항목별 평가 점수를 참고해, 현실적인 대응 전략을 3~4개 단계별로 번호를 붙여 제시하세요."),
        ("human", "{regulation_text}\n{impact_score_detail}")
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return prompt | llm

def render_products_table(products: List[Dict[str, Any]]) -> str:
    table_header = "| 제품명 | 브랜드 | 조치 |\n|---|---|---|"
    rows = [f"| {p.get('product_name','')} | {p.get('brand','-')} | {p.get('action','-')} |" for p in products]
    return "\n".join([table_header] + (rows if rows else ["| - | - | - |"]))

def render_links(links: List[Dict[str, str]]) -> str:
    return "\n".join(
        f"- [{l['title']}]({l['url']})" for l in links
        if l.get("title") and l.get("url")
    ) or "없음"

def render_impact_score_detail(impact_score: Dict[str, Any]) -> str:
    # 개별 항목 점수 표기 및 사유
    items = [
        ("① 직접성", impact_score.get("directness", "-"), "제품·포장·공정에 직접 영향 여부"),
        ("② 법적 강제성", impact_score.get("legal_severity", "-"), "위반 시 법적 제재 강도"),
        ("③ 범위", impact_score.get("scope", "-"), "영향 대상 매출 비중"),
        ("④ 법적 시급성", impact_score.get("regulatory_urgency", "-"), "시행일까지 남은 기간"),
        ("⑤ 운영상 시급성", impact_score.get("operational_urgency", "-"), "운영상 대응 부담"),
        ("⑥ 대응 비용", impact_score.get("response_cost", "-"), "공정·인력·설비 비용")
    ]
    detail_md = "| 평가 항목 | 점수 | 설명 |\n|---|---|---|"
    for name, score, desc in items:
        detail_md += f"\n| {name} | {score} | {desc} |"
    reasoning = impact_score.get("reasoning", "")
    weighted_score = impact_score.get("weighted_score", "-")
    impact_level = impact_score.get("impact_level", "-")
    summary_line = f"\n\n최종 영향도: {impact_level} (합산 점수: {weighted_score})"
    if reasoning: summary_line += f"\n- 평가 사유: {reasoning}"
    return detail_md + summary_line

async def render_report_with_llm(state: AppState) -> str:
    meta = state.metadata or {}
    impact_score = getattr(state, "impact_score", {})
    regulation_text = getattr(state, "regulation_text", "") or meta.get("summary", "-")
    impact_score_detail = render_impact_score_detail(impact_score)

    # 1. 변경요약
    llm_change_summary_chain = get_llm_change_summary_chain()
    change_summary_resp = await llm_change_summary_chain.ainvoke({
        "regulation_text": regulation_text, "impact_score_detail": impact_score_detail
    })
    change_summary = change_summary_resp.content.strip() if change_summary_resp else regulation_text

    section1 = dedent(f"""\
    #### 1. 규제 변경 요약
    국가 / 지역: {meta.get('country','-')} ({meta.get('region','-')})
    규제 카테고리: {meta.get('category','-')}
    변경 요약: {change_summary}
    """).strip()

    # 2. 영향받는 제품 목록(마크다운 표)
    mapped_products = getattr(state, "product_list", [])
    section2 = "#### 2. 영향받는 제품 목록\n\n" + render_products_table(mapped_products)

    # 3. 영향 평가 상세(마크다운 표)
    section3_impact_eval = "#### 3. 영향평가 상세\n" + impact_score_detail

    # 4. 주요 변경 사항 해석 LLM
    llm_analysis_chain = get_llm_analysis_chain()
    analysis_resp = await llm_analysis_chain.ainvoke({
        "regulation_text": regulation_text, "impact_score_detail": impact_score_detail
    })
    section4 = "#### 4. 주요 변경 사항 해석\n" + (analysis_resp.content.strip() if analysis_resp else "- 세부 내용 없음")

    # 5. 대응 전략 LLM
    llm_strategy_chain = get_llm_strategy_chain()
    strategy_resp = await llm_strategy_chain.ainvoke({
        "regulation_text": regulation_text, "impact_score_detail": impact_score_detail
    })
    section5 = "#### 5. 대응 전략 제안\n" + (strategy_resp.content.strip() if strategy_resp else "- 대응 전략 없음")

    # 6. 참고 및 원문 링크
    reference_links = getattr(state, "reference_links", [])
    section6 = "#### 6. 참고 및 원문 링크\n" + render_links(reference_links)

    header = "# SUMMARY REPORT\n규제별 요약 리포트\n---"
    return "\n\n".join([header, section1, section2, section3_impact_eval, section4, section5, section6])

async def report_node(state: AppState) -> Dict[str, Any]:
    """
    LangGraph Report Node - 영향평가 항목 반영 LLM 기반 구조
    """
    report_summary = await render_report_with_llm(state)
    db_session = get_db_session()
    repo = ReportRepository()
    report_data = {
        "created_reason": "AI pipeline auto-generated",
        "translation_id": getattr(state, "translation_id", None),
        "change_id": getattr(state, "change_id", None),
        "product_id": getattr(state, "product_id", None),
        "country_code": (state.metadata or {}).get("country_code", None)
    }
    items_data = []
    summaries_data = [{"impact_score_id": getattr(state, "impact_score_id", None), "summary_text": report_summary}]
    try:
        report_record = await repo.create_with_items(db_session, report_data, items_data, summaries_data)
        await db_session.commit()
        report_id = report_record.report_id
        saved_to_db = True
    except Exception:
        await db_session.rollback()
        report_id = None
        saved_to_db = False
    finally:
        await db_session.close()

    return {
        "report_summary": report_summary,
        "report_data": {
            "report_id": report_id,
            "regulation_id": getattr(state, "regulation_id", None),
            "generated_at": datetime.utcnow().isoformat(),
            "generation_method": "LLM_IMPACT_TEMPLATE",
            "saved_to_db": saved_to_db
        }
    }


# ======== 테스트 코드 예시 ========
if __name__ == "__main__":
    import asyncio

    dummy_state = AppState(
        regulation_text = (
            "유럽연합(EU)은 2025년 12월 1일부터 담배 제품의 니코틴 함량을 0.01mg 단위로 강화 표시해야 하며, "
            "경고문 추가와 표기 방식 표준화를 의무화합니다. 미준수시 판매 제한 및 벌금 등 강한 제재가 부과됩니다. "
            "이번 개정은 청소년 흡연율 감소와 소비자 보호 투명성 확보가 목표입니다."
        ),
        metadata = {
            "country": "유럽연합",
            "region": "EU",
            "category": "라벨 표시 – 니코틴 함량 표기",
            "summary": "니코틴 함량 표시 강화 · 경고문 의무화 · 미준수 시 강력 제재"
        },
        impact_score = {
            "directness": 1,
            "legal_severity": 5,
            "scope": 4,
            "regulatory_urgency": 4,
            "operational_urgency": 2,
            "response_cost": 3,
            "weighted_score": 3.9,
            "impact_level": "High",
            "reasoning": (
                "EU 니코틴 기준은 전 제품 라벨/포장 설계에 직접적 영향을 주며, "
                "위반시 판매금지·벌금 가능성이 크고, 시급한 라벨 변경 등이 필요함. "
                "전체 제품 매출 중 60% 이상이 해당되고, 시행까지 2개월 남음. "
                "내부 R&D 승인 및 디자인 변경, 비용은 디자인수정·재고관리 수준."
            )
        },
        product_list = [
            {"product_name": "VapeX Mint 20mg", "brand": "SmokeFree Co.", "action": "라벨 수정 필요"},
            {"product_name": "CloudHit Berry 15mg", "brand": "PureVapor", "action": "라벨 수정 필요"}
        ],
        reference_links = [
            {
                "title": "Directive 2014/40/EU – Tobacco Products Directive (TPD)",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32014L0040"
            },
            {
                "title": "EU Official Journal L127/1 – Amendments on Nicotine Labeling",
                "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L:2014:127:FULL"
            }
        ]
    )

    async def test():
        result = await report_node(dummy_state)
        print(result["report_summary"])

    asyncio.run(test())
# from __future__ import annotations

# import logging
# from datetime import datetime

# from app.ai_pipeline.state import AppState

# logger = logging.getLogger(__name__)


# async def report_node(state: AppState) -> AppState:
#     """
#     보고서 생성 placeholder.

#     실제 리포트 생성 로직이 준비될 때까지는 간단한 메타데이터만 채워준다.
#     """

#     logger.info("report_node 실행 (placeholder)")
#     state["report"] = {
#         "generated_at": datetime.utcnow().isoformat() + "Z",
#         "status": "draft",
#         "sections": [],
#     }
#     return state


# __all__ = ["report_node"]
