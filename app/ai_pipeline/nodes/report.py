"""
app/ai_pipeline/nodes/report.py
ReportAgent – 구조화 JSON 보고서 생성 & RDB 연동 가능 버전
"""

import os
from datetime import datetime
from typing import Any, Dict, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.ai_pipeline.state import AppState

# DB 연동 예시 (각 환경에 맞게 주석 해제/구현)
# from app.core.repositories.report_repository import ReportRepository
# from app.core.database import get_db_session

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")


def build_sections(state: AppState, llm_struct: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = state.get("product_info", {})
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    strategy = state.get("strategy", {})
    strategy_items = strategy.get("items", [])
    impact_score = (state.get("impact_scores", []) or [{}])[0]

    # 제품 표 추출
    product_table = [
        {
            "제품명": item.get("feature_name", ""),
            "브랜드": item.get("product_id", ""),
            "조치": f"현재: {item.get('current_value', '-')}, 필요: {item.get('required_value','-')}"
        } for item in mapping_items
    ]

    # 참고 링크 추출
    references = []
    for item in mapping_items:
        meta_link = item.get("regulation_meta", {})
        if meta_link.get("source_url"):
            references.append({
                "title": item.get("regulation_chunk_id", ""),
                "url": meta_link.get("source_url")
            })

    # 빈값 대응 (Fallback)
    major_analysis = llm_struct.get("major_analysis")
    if not major_analysis:
        major_analysis = [
            "규제 적용 제품의 포장/성분 변경 필요",
            "해당 규제 미준수 시 벌금 및 회수 위험",
            "법적 요건 충족 위해 함량 조정 필수"
        ]
    strategy_steps = llm_struct.get("strategy")
    if not strategy_steps:
        strategy_steps = [
            "즉시 제품 성분 조정 계획 수립",
            "포장 및 라벨링 변경 스케쥴 준비",
            "법적 컨설팅 및 관계 부처와 협의 시작"
        ]

    return [
        {
            "key": "regulation_summary",
            "title": "1. 규제 변경 요약",
            "content": {
                "country": meta.get("country", ""),
                "region": meta.get("region", ""),
                "category": mapping_items[0].get("parsed",{}).get("category","") if mapping_items else "",
                "summary": mapping_items[0].get("regulation_summary","") if mapping_items else "",
                "impact_level": impact_score.get("impact_level","N/A"),
                "impact_score": impact_score.get("weighted_score", 0.0),
            }
        },
        {
            "key": "product_table",
            "title": "2. 영향받는 제품 목록",
            "table": product_table
        },
        {
            "key": "major_analysis",
            "title": "3. 주요 변경 사항 해석",
            "bullets": major_analysis
        },
        {
            "key": "strategy",
            "title": "4. 대응 전략 제안",
            "steps": strategy_steps
        },
        {
            "key": "references",
            "title": "5. 참고 및 원문 링크",
            "links": references
        }
    ]

def get_llm_brief_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "아래 데이터를 참고해 '주요 변경 사항 해석(bullet 3개)', '대응 전략 steps(3개)' JSON만 생성하세요. 입력이 부족해도 빈 bullet/step 없이 임의의 합리적 예시 반환하세요."),
        ("human", "{input}")
    ])
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    return prompt | llm

async def get_llm_structured_summary(context: str) -> Dict[str, Any]:
    chain = get_llm_brief_chain()
    response = await chain.ainvoke({"input": context})
    try:
        result = eval(response.content)
        if not isinstance(result, dict):
            raise ValueError
    except Exception:
        result = {
            "major_analysis": [
                "규제 적용 제품의 포장/성분 변경 필요",
                "해당 규제 미준수 시 벌금 및 회수 위험",
                "법적 요건 충족 위해 함량 조정 필수"
            ],
            "strategy": [
                "즉시 제품 성분 조정 계획 수립",
                "포장 및 라벨링 변경 스케쥴 준비",
                "법적 컨설팅 및 관계 부처와 협의 시작"
            ]
        }
    return result

async def report_node(state: AppState) -> Dict[str, Any]:
    meta = state.get("product_info", {})
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    strategy = state.get("strategy", {})
    strategy_items = strategy.get("items", [])
    impact_score = (state.get("impact_scores", []) or [{}])[0]

    context_parts = [
        f"국가: {meta.get('country','')}, 지역: {meta.get('region','')}",
        f"규제 요약: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
        f"영향도: {impact_score.get('impact_level','N/A')} ({impact_score.get('weighted_score',0.0)})",
        f"제품 정보: {mapping_items[0].get('feature_name','')} {mapping_items[0].get('current_value','')}" if mapping_items else "",
        f"전략 권고사항: {strategy_items[0].get('recommendation','') if strategy_items else ''}",
        f"영향 평가 reasoning: {impact_score.get('reasoning','')}"
    ]
    llm_context = "\n".join([part for part in context_parts if part])

    llm_struct = await get_llm_structured_summary(llm_context)
    sections = build_sections(state, llm_struct)

    report_json = {
        "report_id": None,
        "generated_at": datetime.utcnow().isoformat(),
        "sections": sections
    }

    # RDB 저장 주석 예시 (프로젝트 환경에 맞게 구현)
    # db_session = get_db_session()
    # repo = ReportRepository(db_session)
    # report_id = await repo.create_report_json(report_json)
    # await db_session.commit()
    # await db_session.close()
    # report_json["report_id"] = report_id

    return report_json

# ================================
# 단독 더미데이터 실행/검증 코드
# ================================
if __name__ == "__main__":
    import asyncio

    dummy_state: AppState = {
        "product_info": {
            "product_id": "VAP-002",
            "country": "EU",
            "region": "유럽연합(EU)",
            "features": {"nicotine_concentration": 15},
            "feature_units": {"nicotine_concentration": "mg"}
        },
        "mapping": {
            "product_id": "VAP-002",
            "items": [
                {
                    "product_id": "VAP-002",
                    "feature_name": "nicotine_concentration",
                    "applies": True,
                    "required_value": 10,
                    "current_value": 15,
                    "gap": 5,
                    "regulation_chunk_id": "EU-TPD-01",
                    "regulation_summary": "니코틴 함량은 10mg 이하로 제한됨",
                    "regulation_meta": {"source_url": "https://example.com/eu_tpd"},
                    "parsed": {
                        "category": "nicotine",
                        "requirement_type": "max",
                        "condition": "<=10"
                    }
                }
            ]
        },
        "strategy": {
            "product_id": "VAP-002",
            "items": [
                {
                    "feature_name": "nicotine_concentration",
                    "regulation_chunk_id": "EU-TPD-01",
                    "impact_level": "High",
                    "summary": "니코틴 제한 초과",
                    "recommendation": "니코틴 함량 조정 및 신규 라벨 디자인 필요"
                }
            ]
        },
        "impact_scores": [
            {
                "impact_level": "High",
                "weighted_score": 4.8,
                "reasoning": "니코틴 함량이 규제 기준을 초과하여 즉시 교정이 필요하며, 벌금 및 시장 퇴출 위험 존재"
            }
        ]
    }

    async def main():
        result = await report_node(dummy_state)
        import json
        print("=" * 60)
        print("생성 구조화 리포트 JSON:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("=" * 60)
        print("섹션별 예시:")
        for sec in result["sections"]:
            print(f"--- {sec['title']} ---")
            print(sec)

    asyncio.run(main())
