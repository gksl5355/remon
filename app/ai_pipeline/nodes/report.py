"""
app/ai_pipeline/nodes/report.py
ReportAgent – 구조화 JSON 보고서 생성 & RDB 연동 가능 버전
"""

import os
import json
import re
import logging
import json
import re
import os
from datetime import datetime
from typing import Any, Dict, List
from dotenv import load_dotenv

from openai import OpenAI
from app.ai_pipeline.state import AppState

# DB 연동
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

load_dotenv()
logger = logging.getLogger(__name__)
client = OpenAI()

# DB 연동 예시 (각 환경에 맞게 주석 해제/구현)
# from app.core.repositories.report_repository import ReportRepository
# from app.core.database import get_db_session

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

# 전략 LLM 재사용 (실패 시 None으로 두고 fallback 사용)
try:  # pragma: no cover - import guard
    from app.ai_pipeline.nodes.llm import llm as strategy_llm
except Exception:
    strategy_llm = None


# -----------------------------
# LLM 구조화 JSON 생성
# -----------------------------
async def get_llm_structured_summary(context: str) -> Dict[str, Any]:
    prompt = f"""
당신은 규제 분석 전문가입니다.

아래 데이터를 기반으로 JSON만 생성하세요.

JSON 최상위 키는 다음 두 개여야 합니다:
1. "major_analysis": 3개의 문자열 리스트
2. "strategies": 3개의 문자열 리스트

마크다운 없이 순수 JSON만 출력하세요.

[데이터]
{context}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
            ],
            temperature=0.0,
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r"```json|```", "", text)
        return json.loads(text)

    except Exception as e:
        logger.error(f"[ReportNode] JSON 파싱 실패: {e}")
        return {}   # fallback


# -----------------------------
# 섹션 생성
# -----------------------------
def build_sections(state: AppState, llm_struct: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = state.get("product_info", {})
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    strategies = state.get("strategies", [])
    impact_score = (state.get("impact_scores") or [{}])[0]

    # fallback data
    major_analysis = llm_struct.get("major_analysis") or [
        "(빈값 대응) 주요 변경사항 분석 부족"
    ]
    strategy_steps = llm_struct.get("strategies") or [
        "(빈값 대응) 전략 수립 데이터 부족"
    ]

    product_rows = [
        [
            item.get("feature_name", ""),
            item.get("product_name", ""),
            f"현재: {item.get('current_value', '-')}, 필요: {item.get('required_value','-')}"
        ]
        for item in mapping_items
    ]

    references = []
    for item in mapping_items:
        url = item.get("regulation_meta", {}).get("source_url")
        if url:
            references.append({
                "title": item.get("regulation_chunk_id", ""),
                "url": url
            })

    summary_content = [
        f"국가 / 지역: {meta.get('country', '')} ({meta.get('region', '')})",
        f"카테고리: {mapping_items[0].get('parsed',{}).get('category','') if mapping_items else ''}",
        f"규제 요약: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
        f"영향도: {impact_score.get('impact_level','N/A')} (점수 {impact_score.get('weighted_score',0.0)})",
        f"전략 권고: {strategies[0] if strategies else ''}"
    ]

    return [
        {
            "id": "summary",
            "title": "1. 규제 변경 요약",
            "type": "paragraph",
            "content": summary_content
        },
        {
            "id": "products",
            "title": "2. 영향받는 제품 목록",
            "type": "table",
            "headers": ["규제항목", "제품명", "조치"],
            "rows": product_rows
        },
        {
            "id": "changes",
            "title": "3. 주요 변경 사항 해석",
            "type": "list",
            "content": major_analysis
        },
        {
            "id": "strategy",
            "title": "4. 대응 전략 제안",
            "type": "list",
            "content": strategy_steps
        },
        {
            "id": "reasoning",
            "title": "5. 영향 평가 근거",
            "type": "paragraph",
            "content": [impact_score.get("reasoning", "")]
        },
        {
            "id": "references",
            "title": "6. 참고 및 원문 링크",
            "type": "links",
            "content": references
        }
    ]


# -----------------------------
# 메인 Report Node
# -----------------------------
async def report_node(state: AppState) -> Dict[str, Any]:
    meta = state.get("product_info", {})
    mapping_items = state.get("mapping", {}).get("items", [])
    strategies = state.get("strategies", [])
    impact_score = (state.get("impact_scores") or [{}])[0]
    regulation_trace = meta.get("regulation_trace")

    context_parts = [
        f"국가: {meta.get('country','')}, 지역: {meta.get('region','')}",
        f"요약: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
        f"영향도: {impact_score.get('impact_level','N/A')}",
        f"전략: {strategies[0] if strategies else ''}",
        f"근거: {impact_score.get('reasoning','')}"
    ]
    llm_context = "\n".join(context_parts)

    # 1) LLM으로 구조화된 JSON 생성
    llm_struct = await get_llm_structured_summary(llm_context)

    # 2) 섹션 구성
    sections = build_sections(state, llm_struct)

    # 3) DB 저장
    report_json = {
        "report_id": None,
        "generated_at": datetime.utcnow().isoformat(),
        "sections": sections
    }

    async with AsyncSessionLocal() as db_session:
        from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository
        from app.core.repositories.report_repository import ReportSummaryRepository

        keynote_repo = RegulationKeynoteRepository()
        summary_repo = ReportSummaryRepository()

        try:
            keynote = await keynote_repo.create_keynote(
                db_session,
                [
                    f"country: {meta.get('country', '')}",
                    f"category: {mapping_items[0].get('parsed',{}).get('category','') if mapping_items else ''}",
                    f"summary: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
                    f"impact: {impact_score.get('impact_level','N/A')}"
                ]
            )
            logger.info(f"Keynote 저장 완료: {keynote.keynote_id}")

            summary = await summary_repo.create_report_summary(db_session, sections)
            # 규제 trace 저장
            if regulation_trace:
                pid = meta.get("product_id")
                try:
                    pid_int = int(pid)
                except (TypeError, ValueError):
                    logger.error("Invalid product_id for trace update: %s", pid)
                else:
                    await db_session.execute(
                        text(
                            "UPDATE products SET regulation_trace = :trace WHERE product_id = :pid"
                        ),
                        {"trace": json.dumps(regulation_trace), "pid": pid_int},
                    )
            await db_session.commit()
            report_json["report_id"] = summary.summary_id
            logger.info(f"ReportSummary 저장 완료: {summary.summary_id}")

        except Exception as e:
            await db_session.rollback()
            logger.error(f"ReportNode DB Error: {e}")

    # 4) ⭐ 반드시 state 업데이트 후 return
    state["report"] = report_json
    return state
