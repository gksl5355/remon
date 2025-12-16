"""
app/ai_pipeline/nodes/report.py
ReportAgent – 구조화 JSON 보고서 생성 & RDB 연동 가능 버전
"""

import os
import json
import re
import logging
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
1. "major_analysis": 3개의 문자열 리스트 (각 항목은 완전한 한글 문장)
2. "strategies": 3개의 문자열 리스트 (각 항목은 완전한 한글 문장)

**CRITICAL - 한글 출력 규칙 (반드시 준수)**:
- 모든 설명, 동사, 조사는 반드시 한글로 작성
- 다음만 원문 유지:
  * 고유명사 (제품명, 회사명, 기관명, 법령명)
  * 수치와 단위 (20mg, $1,000, 30%, mAh)
  * 법령 조항 (§1160.5, Article 3, CFR)
  * 국가/지역 코드 (US, KR, EU, FDA)
  * 영문 약어 (PMTA, TPD, ENDS)
- 올바른 예시: "FDA의 §1160.5 조항에 따라 니코틴 함량을 20mg/mL 이하로 제한해야 합니다"
- 잘못된 예시: "Nicotine concentration must be limited to 20mg/mL" (영어 사용 금지)

마크다운 없이 순수 JSON만 출력하세요.

[데이터]
{context}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 규제 분석 보고서를 한글로 작성하는 전문가입니다. CRITICAL: 모든 설명과 문장은 반드시 한글로 작성하세요. 고유명사, 수치, 법령 조항, 국가 코드, 영문 약어만 원문 유지하고 나머지는 절대 영어를 사용하지 마세요.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r"```json|```", "", text)
        return json.loads(text)

    except Exception as e:
        logger.error(f"[ReportNode] JSON 파싱 실패: {e}")
        return {}  # fallback


# -----------------------------
# 섹션 생성
# -----------------------------
def build_sections(state: AppState, llm_struct: Dict[str, Any]) -> List[Dict[str, Any]]:
    meta = state.get("product_info", {})
    mapping = state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    strategies = state.get("strategies", [])
    impact_score = (state.get("impact_scores") or [{}])[0]
    regulation = state.get("regulation", {})

    # fallback data
    major_analysis = llm_struct.get("major_analysis") or [
        "(빈값 대응) 주요 변경사항 분석 부족"
    ]
    strategy_steps = llm_struct.get("strategies") or [
        "(빈값 대응) 전략 수립 데이터 부족"
    ]

    # product_name은 mapping에서 가져오기
    product_name = mapping.get("product_name", "Unknown")

    # country 정보 우선순위: product_info > regulation > mapping
    country = (
        meta.get("country")
        or regulation.get("country")
        or regulation.get("jurisdiction_code")
        or mapping.get("country")
        or ""
    )

    # ✅ 제품별로 그룹화 (feature 중복 제거)
    from collections import defaultdict

    product_groups = defaultdict(dict)  # {product_name: {feature_name: row}}

    logger.info(f"📊 mapping_items 개수: {len(mapping_items)}")

    for item in mapping_items:
        feature_name = item.get("feature_name", "")
        item_product_name = item.get("product_name") or product_name

        logger.info(f"  - 제품: {item_product_name} / feature: {feature_name}")

        # required_value 표시
        reasoning = item.get("reasoning", "")
        required_value = item.get("required_value")
        if required_value is None:
            reasoning_lower = reasoning.lower()
            if "not regulated" in reasoning_lower or "규제하지 않" in reasoning:
                required_display = "규제 대상 아님"
            elif "already compliant" in reasoning_lower or "충족" in reasoning:
                required_display = "기준 충족"
            elif (
                "unrelated" in reasoning_lower
                or "무관" in reasoning
                or "비적용" in reasoning
            ):
                required_display = "해당 없음"
            else:
                required_display = "규제 없음"
        else:
            required_display = str(required_value)

        # 🔑 feature별 중복 제거 (첫 번째만 유지)
        if feature_name not in product_groups[item_product_name]:
            product_groups[item_product_name][feature_name] = [
                feature_name,
                f"현재: {item.get('current_value', '-')}, 필요: {required_display}",
                reasoning,
            ]

    # 참고 문헌 생성: Legacy + New 규제 모두 포함
    references_map = {}  # regulation_id를 키로 중복 제거

    def add_regulation_reference(reg_meta: Dict[str, Any], label: str = ""):
        """규제 메타데이터를 references_map에 추가."""
        if not reg_meta:
            return

        reg_id = reg_meta.get("regulation_id")
        if not reg_id or reg_id in references_map:
            return

        title = reg_meta.get("title") or "규제 문서"
        citation = reg_meta.get("citation_code")
        source_url = reg_meta.get("source_url")
        file_path = reg_meta.get("file_path")
        s3_key = reg_meta.get("s3_key")
        effective_date = reg_meta.get("effective_date")
        jurisdiction = reg_meta.get("jurisdiction_code") or reg_meta.get("country")

        # URL 우선순위: 1) source_url 2) S3 경로 3) 로컬 파일명
        if source_url:
            link = source_url
        elif s3_key:
            link = f"s3://remon-regulations/{s3_key}"
        elif file_path:
            from pathlib import Path

            filename = Path(file_path).name
            link = f"파일: {filename}"
        else:
            link = "원문 링크 없음"

        display_title = f"{citation} - {title}" if citation else title
        if label:
            display_title = f"[{label}] {display_title}"

        references_map[reg_id] = {
            "title": display_title,
            "url": link,
            "file_path": file_path or s3_key,  # 있으면 표시, 없으더라도 None
            "citation": citation,
            "effective_date": effective_date,
            "jurisdiction": jurisdiction,
            "regulation_type": label,
        }

    # 1) 새로운 규제 추가
    new_reg_meta = state.get("regulation", {})
    add_regulation_reference(new_reg_meta, "New")

    # 2) Legacy 규제 추가 (change_context에서)
    change_summary = state.get("change_summary") or {}
    legacy_regulation_id = change_summary.get("legacy_regulation_id") if change_summary else None

    if legacy_regulation_id:
        change_context = state.get("change_context", {})
        legacy_regul_data = change_context.get("legacy_regul_data")

        if legacy_regul_data:
            # legacy_regul_data에서 regulation 메타 추출
            legacy_reg_meta = legacy_regul_data.get("regulation", {})
            add_regulation_reference(legacy_reg_meta, "Legacy")

    # 리스트로 변환 (Legacy → New 순서)
    references = (
        sorted(
            references_map.values(),
            key=lambda x: 0 if x.get("regulation_type") == "Legacy" else 1,
        )
        if references_map
        else []
    )

    summary_content = [
        f"국가 / 지역: {country} ({meta.get('region', '')})",
        f"카테고리: {mapping_items[0].get('parsed',{}).get('category','') if mapping_items else ''}",
        f"규제 요약: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
        f"영향도: {impact_score.get('impact_level','N/A')} (점수 {impact_score.get('weighted_score',0.0)})",
        f"전략 권고: {strategies[0] if strategies else ''}",
    ]

    # 0. 종합 요약 (기존 summary)
    overall_summary = {
        "id": "overall_summary",
        "type": "paragraph",
        "title": "0. 종합 요약",
        "content": summary_content,
    }

    # 1. 규제 변경 요약 (change_detection_results 활용)
    change_items = []
    change_results = state.get("change_detection_results") or []  # ✅ None 방지

    logger.info(f"🔍 변경 감지 결과 처리: {len(change_results)}개")

    for idx, result in enumerate(change_results):
        change_detected = result.get("change_detected")
        logger.debug(
            f"  [{idx}] section={result.get('section_ref')}, detected={change_detected}"
        )

        if not change_detected:
            continue

        section = result.get("section_ref", "Unknown")
        numerical_changes = result.get("numerical_changes", [])

        if numerical_changes:
            for num_change in numerical_changes:
                field = num_change.get("field", "항목")
                legacy_val = num_change.get("legacy_value", "없음")
                new_val = num_change.get("new_value", "없음")
                change_items.append(f"- {section}: {field} {legacy_val} → {new_val}")
        else:
            change_type = result.get("change_type", "변경")
            change_items.append(f"- {section}: {change_type}")

    logger.info(f"✅ 변경 항목 생성: {len(change_items)}개")

    change_summary_section = {
        "id": "change_summary",
        "type": "list",
        "title": "1. 규제 변경 요약",
        "content": change_items if change_items else ["변경 사항 없음"],
    }

    # ✅ 제품별 하위 테이블 생성 (중복 제거된 데이터)
    product_tables = []
    for prod_name, features_dict in sorted(product_groups.items()):
        rows = list(features_dict.values())  # dict → list
        product_tables.append(
            {
                "product_name": prod_name,
                "headers": ["제품 속성", "현재 vs 필요", "판단 근거"],
                "rows": rows if rows else [["데이터 없음", "-", "-"]],
            }
        )

    # ✅ 3. 제품 분석 (단일 섹션, 하위 테이블 포함)
    products_section = {
        "id": "products_analysis",
        "type": "nested_tables",
        "title": "3. 제품 분석",
        "tables": product_tables,
    }

    logger.info(f"📊 제품 테이블 생성: {len(product_tables)}개 제품")

    # 🔍 디버깅: 각 섹션 크기 확인
    sections_list = [
        overall_summary,
        change_summary_section,
        {
            "id": "changes",
            "type": "list",
            "title": "2. 주요 변경 사항 해석",
            "content": major_analysis,
        },
        products_section,
        {
            "id": "reasoning",
            "type": "paragraph",
            "title": "4. 영향 평가 근거",
            "content": [impact_score.get("reasoning", "")],
        },
        {
            "id": "strategy",
            "type": "list",
            "title": "5. 대응 전략 제안",
            "content": strategy_steps,
        },
        {
            "id": "references",
            "type": "links",
            "title": "6. 참고 및 원문 링크",
            "content": references,
        },
    ]
    
    logger.info("🔍 [DEBUG] build_sections 반환값 분석")
    for idx, section in enumerate(sections_list):
        section_json = json.dumps(section, ensure_ascii=False)
        logger.info(f"  [{idx}] {section.get('id')}: {len(section_json):,} chars")
    
    return sections_list


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
        f"unknown={unknown} report generated.| global 17팀 대장 고서아"
    )


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
        resp = requests.post(url, json={"text": message}, timeout=10)
        if resp.status_code >= 300:
            logger.warning(
                "Slack 전송 실패: status=%s body=%s", resp.status_code, resp.text
            )
            return False
        logger.info("✅ Slack 알림 전송 완료")
        return True
    except Exception as exc:
        logger.warning("Slack 전송 예외: %s", exc)
        return False


# -----------------------------
# 메인 Report Node
# -----------------------------
async def report_node(state: AppState) -> Dict[str, Any]:
    meta = state.get("product_info") or {}
    mapping_items = state.get("mapping", {}).get("items", [])
    strategies = state.get("strategies", [])
    impact_score = (state.get("impact_scores") or [{}])[0]
    regulation_trace = meta.get("regulation_trace") if meta else None

    context_parts = [
        f"국가: {meta.get('country','')}, 지역: {meta.get('region','')}",
        f"요약: {mapping_items[0].get('regulation_summary','') if mapping_items else ''}",
        f"영향도: {impact_score.get('impact_level','N/A')}",
        f"전략: {strategies[0] if strategies else ''}",
        f"근거: {impact_score.get('reasoning','')}",
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
        "sections": sections,
    }

    async with AsyncSessionLocal() as db_session:
        from app.core.repositories.report_repository import ReportSummaryRepository

        summary_repo = ReportSummaryRepository()

        try:
            # Change Detection Keynote는 change_detection 노드에서 이미 저장됨 (중복 제거)
            summary = await summary_repo.create_report_summary(db_session, sections)
            await db_session.commit()  # 즉시 commit
            report_json["report_id"] = summary.summary_id
            logger.info(f"ReportSummary 저장 완료: {summary.summary_id}")
            
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

        except Exception as e:
            await db_session.rollback()
            logger.error(f"ReportNode DB Error: {e}")

    # 4) Slack 알림 전송
    try:
        mapping = state.get("mapping", {})
        product_name = mapping.get("product_name", "Unknown")
        regulation = state.get("regulation", {})
        country = regulation.get("country", "Unknown")
        regulation_title = regulation.get("title", "규제명 없음")
        impact_level = impact_score.get("impact_level", "N/A")
        
        # 유효 카테고리 추출
        valid_features_set = set()
        for item in mapping_items:
            if item.get("applies"):
                valid_features_set.add(item.get("feature_name"))
        
        valid_features = sorted(list(valid_features_set))
        valid_features_str = ", ".join(valid_features[:2]) if valid_features else "없음"
        
        # Key Change 추출 (우선순위: change_detection_results > mapping fallback)
        key_change = "No changes detected"
        change_results = state.get("change_detection_results", [])
        
        if change_results:
            high_conf = [c for c in change_results if c.get("confidence_level") == "HIGH" and c.get("change_detected")]
            if high_conf:
                first = high_conf[0]
                key_change = f"{first.get('section_ref', '')}: {first.get('change_type', 'updated')}"
        else:
            # Fallback: mapping에서 category + summary 추출
            if mapping_items:
                category = mapping_items[0].get("parsed", {}).get("category", "")
                summary = mapping_items[0].get("regulation_summary", "")[:100]
                if category and summary:
                    key_change = f"[{category}] {summary}..."
        
        report_id = report_json.get('report_id', 'N/A')
        report_url = "https://ingress.skala25a.project.skala-ai.com/skala2-4-17/"
        
        slack_message = f":bell: REMON 보고서 생성 완료 ({country})\n규제명칭: {regulation_title}\n영향도: {impact_level} | 매핑 항목: {len(valid_features)}개 유효 카테고리 ({valid_features_str})\n제품: {product_name}\nKey Change: {key_change}\nREMON-{report_id} | <{report_url}|Open in REMON>"
        
        send_slack_notification(slack_message)
    except Exception as e:
        logger.warning(f"Slack 알림 전송 실패 (무시): {e}")

    # 5) ⭐ 반드시 state 업데이트 후 return
    state["report"] = report_json
    return state
