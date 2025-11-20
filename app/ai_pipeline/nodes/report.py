"""
app/ai_pipeline/nodes/report.py
ReportAgent - 최종 요약 리포트 생성 노드
Production-ready version with full AppState integration
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from textwrap import dedent
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.ai_pipeline.state import AppState, MappingItem, StrategyItem

# .env에서 OPENAI_API_KEY 로드
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")


def extract_report_data(state: AppState) -> Dict[str, Any]:
    """AppState에서 리포트 생성에 필요한 데이터 추출"""
    
    # 매핑 결과
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", []) if mapping else []
    product_id = mapping.get("product_id", "N/A") if mapping else "N/A"
    
    # 전략 결과
    strategy = state.get("strategy", {})
    strategy_items = strategy.get("items", []) if strategy else []
    
    # 영향도 점수
    impact_scores = state.get("impact_scores", [])
    
    # 제품 정보
    product_info = state.get("product_info", {})
    
    # 전처리 요청 정보 (메타데이터 추출용)
    preprocess_req = state.get("preprocess_request", {})
    
    return {
        "product_id": product_id,
        "product_info": product_info,
        "mapping_items": mapping_items,
        "strategy_items": strategy_items,
        "impact_scores": impact_scores,
        "preprocess_req": preprocess_req
    }


def build_product_table(mapping_items: List[MappingItem]) -> List[Dict[str, str]]:
    """매핑 결과를 제품 테이블로 변환"""
    table = []
    for item in mapping_items:
        if item.get("applies", False):
            table.append({
                "name": item.get("feature_name", ""),
                "brand": item.get("product_id", ""),
                "action": f"현재: {item.get('current_value', 'N/A')}, 필요: {item.get('required_value', 'N/A')}"
            })
    return table


def calculate_impact_summary(impact_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """영향도 점수 요약"""
    if not impact_scores:
        return {"level": "N/A", "score": 0.0, "reasoning": "영향도 데이터 없음"}
    
    # 첫 번째 영향도 점수 사용 (또는 평균 계산 가능)
    first_score = impact_scores[0] if impact_scores else {}
    
    return {
        "level": first_score.get("impact_level", "N/A"),
        "score": first_score.get("weighted_score", 0.0),
        "reasoning": first_score.get("reasoning", "")
    }


def render_md_report(
    product_id: str,
    regulation_summary: str,
    impact_summary: Dict[str, Any],
    product_table: List[Dict[str, str]],
    major_analysis: str,
    strategies: List[str],
    reference_links: List[Dict[str, str]]
) -> str:
    """마크다운 리포트 템플릿 생성"""
    
    block1 = dedent(f"""
    #### 1. 규제 변경 요약
    제품 ID: {product_id}
    규제 내용: {regulation_summary}
    영향도: {impact_summary['level']} (Score: {impact_summary['score']:.2f})
    """).strip()

    block2_rows = [
        f"| {row.get('name', '')} | {row.get('brand', '')} | {row.get('action', '')} |" 
        for row in product_table
    ] or ["| - | - | - |"]
    
    block2 = dedent(f"""
    #### 2. 영향받는 제품 목록

    | Feature | Product ID | 조치사항 |
    | --- | --- | --- |
    {chr(10).join(block2_rows)}
    """).strip()

    block3 = f"#### 3. 주요 변경 사항 해석\n{major_analysis.strip()}"
    
    block4 = "#### 4. 대응 전략 제안\n" + (
        "\n".join([f"{i+1}차 대응: {item.strip()}" for i, item in enumerate(strategies)]) 
        if strategies else "- 전략 정보 없음"
    )
    
    block5 = "#### 5. 참고 및 원문 링크\n" + (
        "".join([f"- [{l['title']}]({l['url']})\n" for l in reference_links])
        if reference_links else "- 참고 링크 없음"
    )

    blocks = [
        "# SUMMARY REPORT\n규제 분석 요약 리포트\n---",
        block1, "---",
        block2, "---",
        block3, "---",
        block4, "---",
        block5.strip()
    ]
    return "\n".join(blocks)


def get_llm_brief_chain():
    """주요 해석과 전략 제안 자동 생성용 LLM 체인"""
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "아래 규제 매핑 결과와 영향 평가를 참고하여 "
         "'주요 변경 사항 해석'(bullet 리스트)과 '대응 전략 제안'(번호 형식)을 "
         "한글로 명확하게 요약하세요. 각각 3개 이내로 간결하게 작성하세요."),
        ("human",
         "[규제 매핑 결과]\n{mapping_summary}\n\n"
         "[영향 평가 사유]\n{impact_reasoning}\n\n"
         "[전략 권고사항]\n{strategy_summary}")
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    return prompt | llm


async def generate_summary_sections(
    mapping_items: List[MappingItem],
    impact_reasoning: str,
    strategy_items: List[StrategyItem]
):
    """LLM으로 주요 해석 및 전략 자동 생성"""
    
    # 매핑 요약
    mapping_summary = "\n".join([
        f"- {item.get('feature_name', '')}: {item.get('regulation_summary', '')}"
        for item in mapping_items[:5]  # 상위 5개만
    ]) or "매핑 결과 없음"
    
    # 전략 요약
    strategy_summary = "\n".join([
        f"- {item.get('feature_name', '')}: {item.get('recommendation', '')}"
        for item in strategy_items[:5]  # 상위 5개만
    ]) or "전략 정보 없음"
    
    llm_chain = get_llm_brief_chain()
    response = await llm_chain.ainvoke({
        "mapping_summary": mapping_summary,
        "impact_reasoning": impact_reasoning,
        "strategy_summary": strategy_summary
    })
    
    lines = [l for l in response.content.splitlines() if l.strip()]
    
    # bullet 리스트 (주요 해석)
    bullets = [l for l in lines if l.strip().startswith(("-", "•", "·"))]
    
    # 전략 제안 (번호 형식)
    strategies = [l for l in lines if any(l.startswith(f"{i}차") for i in range(1, 10))]
    if not strategies:
        strategies = [l for l in lines if l.strip() and l.strip()[0].isdigit() and l not in bullets]
    
    if not bullets and lines:
        bullets = lines[:3]
    if not strategies:
        strategies = lines[-3:] if len(lines) > 3 else lines
    
    return "\n".join(bullets), strategies


async def report_node(state: AppState) -> Dict[str, Any]:
    """
    ReportAgent 진입점 - AppState 기반 요약 리포트 생성
    
    Args:
        state: LangGraph 파이프라인 공유 State
    
    Returns:
        report: ReportDraft 구조
    """
    
    # 1. 데이터 추출
    data = extract_report_data(state)
    
    # 2. 제품 테이블 생성
    product_table = build_product_table(data["mapping_items"])
    
    # 3. 영향도 요약
    impact_summary = calculate_impact_summary(data["impact_scores"])
    
    # 4. 규제 요약 (매핑 결과 기반)
    regulation_summary = ""
    if data["mapping_items"]:
        first_item = data["mapping_items"][0]
        regulation_summary = first_item.get("regulation_summary", "규제 정보 없음")
    else:
        regulation_summary = "규제 매핑 결과 없음"
    
    # 5. LLM으로 주요 해석 및 전략 생성
    major_analysis, strategies = await generate_summary_sections(
        data["mapping_items"],
        impact_summary["reasoning"],
        data["strategy_items"]
    )
    
    # 6. 참고 링크 (매핑 메타데이터에서 추출)
    reference_links = []
    for item in data["mapping_items"][:3]:  # 상위 3개만
        reg_meta = item.get("regulation_meta", {})
        if reg_meta:
            reference_links.append({
                "title": f"규제 문서 - {item.get('regulation_chunk_id', '')}",
                "url": reg_meta.get("source_url", "#")
            })
    
    # 7. 마크다운 리포트 생성
    report_markdown = render_md_report(
        data["product_id"],
        regulation_summary,
        impact_summary,
        product_table,
        major_analysis,
        strategies,
        reference_links
    )
    
    # 8. ReportDraft 구조로 반환
    report_draft = {
        "generated_at": datetime.utcnow().isoformat(),
        "status": "completed",
        "sections": [
            {
                "type": "markdown",
                "content": report_markdown
            }
        ]
    }
    
    return {
        "report": report_draft
    }


# ==========================================
# 단독 테스트 코드
# ==========================================
# if __name__ == "__main__":
    
#     dummy_state: AppState = {
#         "product_info": {
#             "product_id": "PROD-001",
#             "features": {"battery_capacity": 3000},
#             "feature_units": {"battery_capacity": "mAh"}
#         },
#         "mapping": {
#             "product_id": "PROD-001",
#             "items": [
#                 {
#                     "product_id": "PROD-001",
#                     "feature_name": "battery_capacity",
#                     "applies": True,
#                     "required_value": 3500,
#                     "current_value": 3000,
#                     "gap": -500,
#                     "regulation_chunk_id": "REG-001",
#                     "regulation_summary": "배터리 용량 최소 3500mAh 이상 필요",
#                     "regulation_meta": {"source_url": "https://example.com/reg"},
#                     "parsed": {
#                         "category": "battery",
#                         "requirement_type": "min",
#                         "condition": ">=3500"
#                     }
#                 }
#             ]
#         },
#         "strategy": {
#             "product_id": "PROD-001",
#             "items": [
#                 {
#                     "feature_name": "battery_capacity",
#                     "regulation_chunk_id": "REG-001",
#                     "impact_level": "High",
#                     "summary": "배터리 용량 부족",
#                     "recommendation": "배터리 용량 증설 필요"
#                 }
#             ]
#         },
#         "impact_scores": [
#             {
#                 "impact_level": "High",
#                 "weighted_score": 4.2,
#                 "reasoning": "배터리 용량 미달로 인한 규제 위반 위험 높음"
#             }
#         ]
#     }
    
#     async def main():
#         result = await report_node(dummy_state)
#         report = result["report"]
#         print("=" * 60)
#         print("생성된 리포트:")
#         print("=" * 60)
#         print(report["sections"][0]["content"])
#         print("\n" + "=" * 60)
#         print("메타데이터:")
#         print(f"생성 시각: {report['generated_at']}")
#         print(f"상태: {report['status']}")
    
#     asyncio.run(main())
