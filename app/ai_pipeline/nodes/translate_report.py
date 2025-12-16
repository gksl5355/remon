"""
module: translate_report.py
description: LangGraph 번역 노드 - 보고서 sections를 한글로 번역
author: AI Agent
created: 2025-01-18
updated: 2025-01-21 (번역 프롬프트 강화 - 고유명사 제외 전체 번역)
dependencies:
    - openai
    - app.core.database
    - app.ai_pipeline.state
"""

from __future__ import annotations

import logging
import json

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def translate_report_node(state: AppState) -> AppState:
    """
    보고서 전체를 한 번에 번역 (state 우선, DB는 fallback).

    INPUT: state["report"]["sections"] (우선) or DB 조회 (fallback)
    OUTPUT: 번역된 sections를 DB translation 컬럼에 저장
    """
    from openai import AsyncOpenAI
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    logger.info("🌐 번역 노드 시작")

    report = state.get("report")
    if not report or not report.get("report_id"):
        logger.warning("번역할 보고서 ID 없음")
        return state

    report_id = report["report_id"]

    # ✅ state에서 sections 우선 사용 (메모리 효율)
    sections = report.get("sections")

    if not sections:
        # ⚠️ Fallback: DB에서 조회 (예외 모드)
        logger.warning(f"state에 sections 없음, DB 조회 모드로 전환")
        async with AsyncSessionLocal() as db_session:
            result = await db_session.execute(
                text(
                    "SELECT summary_text FROM report_summaries WHERE summary_id = :id"
                ),
                {"id": report_id},
            )
            row = result.fetchone()

            if not row or not row[0]:
                logger.error(f"summary_id={report_id}의 데이터 없음")
                return state

            sections = row[0]  # JSONB 자동 파싱
            logger.info("✅ DB에서 sections 조회 완료")
    else:
        logger.info("✅ state에서 sections 직접 사용 (DB 조회 생략)")

    # 🔍 디버깅: sections 구조 분석
    logger.info("=" * 60)
    logger.info("🔍 [DEBUG] sections 구조 분석")
    logger.info(f"  타입: {type(sections)}")
    logger.info(
        f"  길이: {len(sections) if isinstance(sections, (list, dict)) else 'N/A'}"
    )

    if isinstance(sections, list):
        logger.info(f"  섹션 개수: {len(sections)}개")
        for idx, section in enumerate(sections[:3]):
            logger.info(
                f"  [{idx}] id={section.get('id')}, type={section.get('type')}, title={section.get('title')}"
            )
            content = section.get("content", [])
            if isinstance(content, list):
                logger.info(f"      content: {len(content)}개 항목")
                if content:
                    logger.info(f"      샘플: {str(content[0])[:80]}...")

    # JSON 문자열로 변환
    sections_json = json.dumps(sections, ensure_ascii=False, indent=2)

    logger.info(
        f"📊 번역 대상 크기: {len(sections_json):,} chars ({len(sections_json)/1024:.1f} KB)"
    )
    logger.info(f"  첫 500자: {sections_json[:500]}")
    logger.info("=" * 60)

    # LLM 번역
    client = AsyncOpenAI()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional JSON translator specializing in regulatory documents. Translate ALL non-Korean text to Korean while preserving JSON structure.

CRITICAL TRANSLATION RULES:
1. JSON Structure: Keep EXACTLY as is (keys, arrays, nesting, order)
2. TRANSLATE EVERYTHING except:
   - Numbers: 150, 4.5, 35, 23, 33%, 70%
   - Units: mg, mg/g, mg/kg, mg/mL, mm, mAh, %
   - Legal citations: §1160.5, §1160.7, §1160.15, §1160.18, §1160.25, §Unknown, 21 CFR Part 1160
   - Country/region codes: US, KR, EU, FDA, PMTA, USPS, FedEx, UPS, TPD, ENDS
   - Product names: This, lil, VAPE-X Pro (if proper nouns)
   - Technical IDs: PMTA-Pending-2025, PMTA-2020-005
   - URLs and file paths
   - null, true, false values

3. MUST TRANSLATE (even if mixed with proper nouns):
   - ALL English sentences and phrases
   - ALL descriptive text in "reasoning", "content", "title" fields
   - ALL table headers and labels
   - ALL explanations, even if they contain proper nouns
   - Examples:
     * "N/A (unrelated): §1160.5 addresses nicotine level standards" 
       → "해당 없음 (무관): §1160.5는 니코틴 수준 기준을 다룹니다"
     * "Warning Label Requirements apply to package" 
       → "경고 라벨 요구사항이 패키지에 적용됩니다"
     * "Current package string does not show compliance" 
       → "현재 패키지 문자열은 준수를 보여주지 않습니다"
     * "Adult signature mandatory" 
       → "성인 서명 필수"

4. Output: ONLY valid JSON (no markdown blocks, no explanations)

EXAMPLE:
Before: "N/A (unrelated): §Unknown addresses validation of testing methods and recordkeeping, not flavor"
After: "해당 없음 (무관): §Unknown은 테스트 방법 검증 및 기록 보관을 다루며, 향미는 다루지 않습니다""""",
                },
                {"role": "user", "content": sections_json},
            ],
            temperature=0,
            max_tokens=16384,
        )

        # ✅ LLM 출력을 그대로 사용 (파싱 없음)
        translated_json = response.choices[0].message.content.strip()

        # 마크다운 코드 블록 제거만 수행
        if "```json" in translated_json:
            start = translated_json.find("```json") + 7
            end = translated_json.find("```", start)
            translated_json = translated_json[start:end].strip()
        elif "```" in translated_json:
            start = translated_json.find("```") + 3
            end = translated_json.find("```", start)
            translated_json = translated_json[start:end].strip()
        
        # 🔧 제어 문자 제거 (JSON 파싱 오류 방지)
        import re
        translated_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', translated_json)
        
        # 🔧 과도한 공백 정규화 (LLM 출력 오류 방지)
        translated_json = re.sub(r'\s+', ' ', translated_json)  # 연속 공백 → 단일 공백
        translated_json = re.sub(r'\s*([{}\[\]:,])\s*', r'\1', translated_json)  # 구조 문자 주변 공백 제거

        # ✅ Dict로 래핑 (DB 스키마 호환)
        translation_data = {"sections": json.loads(translated_json)}

        # DB 저장
        async with AsyncSessionLocal() as db_session:
            await db_session.execute(
                text(
                    "UPDATE report_summaries SET translation = CAST(:trans AS jsonb) WHERE summary_id = :id"
                ),
                {
                    "trans": json.dumps(translation_data, ensure_ascii=False),
                    "id": report_id,
                },
            )
            await db_session.commit()
            logger.info(f"✅ 번역 완료: summary_id={report_id}")

    except json.JSONDecodeError as e:
        logger.error(f"❌ 번역 JSON 파싱 실패: {e}")
        logger.error(f"  오류 위치: line {e.lineno}, col {e.colno}, pos {e.pos}")
        logger.error(f"  LLM 응답 길이: {len(translated_json):,} chars")
        logger.error(
            f"  오류 주변 텍스트: {translated_json[max(0, e.pos-100):e.pos+100]}"
        )
        logger.warning("⚠️ 번역 스킵, 원본 데이터 유지")
    except Exception as e:
        logger.error(f"❌ 번역 실패: {e}")
        logger.warning("⚠️ 번역 스킵, 원본 데이터 유지")

    return state


__all__ = ["translate_report_node"]
