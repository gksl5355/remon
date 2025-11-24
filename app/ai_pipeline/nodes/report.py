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
