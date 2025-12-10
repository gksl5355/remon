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
from typing import Any, Dict, List, Optional
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

    # product_name은 mapping에서 가져오기
    product_name = mapping.get("product_name", "Unknown")
    
    # 중복 feature-row를 최소화하기 위해 feature 기준으로 dedupe
    seen_rows = set()
    product_rows = []
    for item in mapping_items:
        feature_name = item.get("feature_name", "")
        if feature_name in seen_rows:
            continue
        seen_rows.add(feature_name)
        
        # reasoning은 이미 LLM에서 250자 이내로 생성됨
        reasoning = item.get("reasoning", "")
        
        # required_value 표시 개선
        required_value = item.get('required_value')
        if required_value is None:
            # reasoning에서 이유 추출
            reasoning_lower = reasoning.lower()
            if "not regulated" in reasoning_lower or "규제하지 않" in reasoning:
                required_display = "규제 대상 아님"
            elif "already compliant" in reasoning_lower or "충족" in reasoning:
                required_display = "기준 충족"
            elif "unrelated" in reasoning_lower or "무관" in reasoning or "비적용" in reasoning:
                required_display = "해당 없음"
            else:
                required_display = "규제 없음"
        else:
            required_display = str(required_value)
        
        product_rows.append(
            [
                feature_name,
                product_name,
                f"현재: {item.get('current_value', '-')}, 필요: {required_display}",
                reasoning,
            ]
        )

    # 참고 문헌 생성 (regulation에서 추출, 중복 제거)
    references_map = {}  # regulation_id를 키로 중복 제거
    
    for item in mapping_items:
        chunk_id = item.get("regulation_chunk_id", "")
        reg_id = chunk_id.split("-")[0] if "-" in chunk_id else chunk_id
        
        if not reg_id or reg_id in references_map:
            continue
        
        # regulation 메타데이터에서 정보 추출
        reg_meta = state.get("regulation", {})
        title = reg_meta.get("title") or "규제 문서"
        citation = reg_meta.get("citation_code")
        url = reg_meta.get("source_url")
        file_path = reg_meta.get("file_path")
        effective_date = reg_meta.get("effective_date")
        jurisdiction = reg_meta.get("jurisdiction_code") or reg_meta.get("country")
        
        # URL 또는 파일 경로 결정
        if url:
            link = url
        elif file_path:
            from pathlib import Path
            link = f"파일: {Path(file_path).name}"
        else:
            link = "원문 링크 없음"
        
        references_map[reg_id] = {
            "title": f"{citation} - {title}" if citation else title,
            "url": link,
            "citation": citation,
            "effective_date": effective_date,
            "jurisdiction": jurisdiction
        }
    
    # 리스트로 변환
    references = list(references_map.values())

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
            "type": "paragraph",
            "title": "1. 규제 변경 요약",
            "content": summary_content
        },
        {
            "id": "products",
            "type": "table",
            "title": "2. 영향받는 제품 목록",
            "headers": ["제품 속성", "제품명", "현재 vs 필요", "판단 근거"],
            "rows": product_rows
        },
        {
            "id": "changes",
            "type": "list",
            "title": "3. 주요 변경 사항 해석",
            "content": major_analysis
        },
        {
            "id": "strategy",
            "type": "list",
            "title": "4. 대응 전략 제안",
            "content": strategy_steps
        },
        {
            "id": "reasoning",
            "type": "paragraph",
            "title": "5. 영향 평가 근거",
            "content": [impact_score.get("reasoning", "")]
        },
        {
            "id": "references",
            "type": "links",
            "title": "6. 참고 및 원문 링크",
            "content": references
        }
    ]


# -----------------------------
# 알림 메시지/슬랙 전송 헬퍼
# -----------------------------
def build_report_notification(mapping: Dict[str, Any], product_name: str = "") -> str:
    """변경 건수와 보고서 생성 완료 메시지를 단순 문자열로 생성."""
    unknown = len(mapping.get("unknown_requirements", []) or [])
    total_items = len(mapping.get("items", []))
    prod = product_name or mapping.get("product_name", "") or "unknown"
    return (
        f"[Report] product={prod} items={total_items} "
        f"unknown={unknown} report generated.| global 17팀 대장 고서아")


def send_slack_notification(message: str, webhook_url: Optional[str] = None) -> bool:
    """
    간단한 Slack Webhook 전송 헬퍼.
    테스트 시 SLACK_WEBHOOK_URL 환경변수나 인자를 지정해야 하며,
    실패해도 예외를 던지지 않고 False 반환.
    """
    import os
    import requests

    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        logger.warning("SLACK_WEBHOOK_URL 미설정 - 슬랙 전송 스킵")
        return False
    try:
        resp = requests.post(url, json={"text": message}, timeout=5)
        if resp.status_code >= 300:
            logger.warning("Slack 전송 실패: status=%s body=%s", resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:
        logger.warning("Slack 전송 예외: %s", exc)
        return False


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
