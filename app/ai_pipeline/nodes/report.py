import os
from datetime import datetime
from typing import Dict, Any, List
from textwrap import dedent

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Any, Dict, List, Optional

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
# 전략 LLM 재사용 (실패 시 None으로 두고 fallback 사용)
try:  # pragma: no cover - import guard
    from app.ai_pipeline.nodes.llm import llm as strategy_llm
except Exception:  # pragma: no cover
    strategy_llm = None  # type: ignore[assignment]


def _build_facts(
    preprocess_summary: Dict[str, Any],
    mapping_results: Dict[str, Any],
    strategies: List[str],
    impact_scores: List[Dict[str, Any]],
) -> str:
    """LLM에 넣을 요약용 사실 문자열을 구성한다."""
    mapping_items = mapping_results.get("items") or []
    mapping_preview = []
    for item in mapping_items[:3]:
        mapping_preview.append(
            f"{item.get('feature_name')}: required={item.get('required_value')} "
            f"current={item.get('current_value')} applies={item.get('applies')}"
        )

    impact_preview = []
    for score in impact_scores[:2]:
        impact_preview.append(
            f"{score.get('impact_level')}/score={score.get('weighted_score')} "
            f"reason={score.get('reasoning', '')[:60]}"
        )

    lines = [
        f"Preprocess status={preprocess_summary.get('status', 'unknown')} "
        f"(processed={preprocess_summary.get('processed_count', 0)}, "
        f"succeeded={preprocess_summary.get('succeeded', 0)}, "
        f"failed={preprocess_summary.get('failed', 0)})",
        f"Mapping items={len(mapping_items)} preview={'; '.join(mapping_preview) or '없음'}",
        f"Strategies count={len(strategies)} preview={'; '.join(strategies[:3]) or '없음'}",
        f"Impact entries={len(impact_scores)} preview={'; '.join(impact_preview) or '없음'}",
    ]
    return "\n".join(lines)


def _call_llm_for_report(facts: str) -> Optional[str]:
    """LLM을 호출해 한국어 보고서 문구를 생성한다."""
    if not strategy_llm:
        return None

    prompt = f"""
다음 파이프라인 실행 결과를 바탕으로 한국어 요약 보고서를 작성해 주세요.
- 각 노드별 성공/실패 여부와 핵심 결과를 한 문단으로 정리해 주세요.
- 너무 길게 쓰지 말고, 실행 상태를 한눈에 볼 수 있도록 간결하게 작성하세요.
- 숫자나 개수는 사실 그대로만 사용하세요. 새로운 수치는 만들지 마세요.

[실행 결과]
{facts}
"""
    try:
        return strategy_llm.invoke(prompt)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM 보고서 생성 실패: %s", exc)
        return None


async def report_node(state: AppState) -> AppState:
    """
    파이프라인 실행 결과를 요약하는 간단한 리포트 노드.
    - preprocess / mapping / strategy / impact / report 생성 여부를 요약한다.
    - 나중에 정식 리포트 템플릿이 준비될 때까지 임시 테스트 용도로 사용한다.
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

    preprocess_summary = state.get("preprocess_summary") or {}
    mapping_results = state.get("mapping") or state.get("mapping_results") or {}
    strategies = state.get("strategies") or []
    impact_scores = state.get("impact_scores") or []

    # 간단한 단계별 상태 판단
    preprocess_status = preprocess_summary.get("status") or "unknown"
    mapping_count = len(mapping_results.get("items") or [])
    strategy_count = len(strategies)
    impact_count = len(impact_scores)

    sections = [
        {
            "title": "Preprocess",
            "status": preprocess_status,
            "detail": f"processed={preprocess_summary.get('processed_count', 0)} "
                      f"succeeded={preprocess_summary.get('succeeded', 0)} "
                      f"failed={preprocess_summary.get('failed', 0)}",
        },
        {
            "title": "Mapping",
            "status": "ok" if mapping_count > 0 else "empty",
            "detail": f"items={mapping_count}",
        },
        {
            "title": "Strategy",
            "status": "ok" if strategy_count > 0 else "empty",
            "detail": f"strategies={strategy_count}",
        },
        {
            "title": "ImpactScore",
            "status": "ok" if impact_count > 0 else "empty",
            "detail": f"entries={impact_count}",
        },
    ]

    # 간단한 텍스트 요약을 함께 저장
    summary_lines = [
        f"Preprocess: {preprocess_status} "
        f"(processed={preprocess_summary.get('processed_count', 0)}, "
        f"succeeded={preprocess_summary.get('succeeded', 0)}, "
        f"failed={preprocess_summary.get('failed', 0)})",
        f"Mapping: {'ok' if mapping_count else 'empty'} (items={mapping_count})",
        f"Strategy: {'ok' if strategy_count else 'empty'} (strategies={strategy_count})",
        f"ImpactScore: {'ok' if impact_count else 'empty'} (entries={impact_count})",
    ]
    summary_text = "\n".join(summary_lines)

    # LLM 보고서 생성 (실패 시 None)
    facts = _build_facts(
        preprocess_summary,
        mapping_results,
        strategies,
        impact_scores,
    )
    llm_report = _call_llm_for_report(facts)

    logger.info("report_node summary:\n%s", summary_text)
    if llm_report:
        logger.info("report_node LLM 보고서:\n%s", llm_report)

    state["report"] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "draft",
        "sections": sections,
        "summary_text": summary_text,
        "llm_report": llm_report,
        "facts": facts,
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
