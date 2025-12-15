"""LangGraph node: translate_report"""

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
                text("SELECT summary_text FROM report_summaries WHERE summary_id = :id"),
                {"id": report_id}
            )
            row = result.fetchone()
            
            if not row or not row[0]:
                logger.error(f"summary_id={report_id}의 데이터 없음")
                return state
            
            sections = row[0]  # JSONB 자동 파싱
            logger.info("✅ DB에서 sections 조회 완료")
    else:
        logger.info("✅ state에서 sections 직접 사용 (DB 조회 생략)")
    
    # JSON 문자열로 변환
    sections_json = json.dumps(sections, ensure_ascii=False, indent=2)
    
    logger.info(f"📊 번역 대상 크기: {len(sections_json)} chars")
    
    # LLM 번역
    client = AsyncOpenAI()
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a JSON translator. Translate ONLY English text to Korean while preserving JSON structure.

RULES:
- Keep JSON structure EXACTLY as is
- Keep: numbers, units (mg, %), citations (§1160.5), country codes, URLs, null values
- Translate: English text in "title", "content" arrays, "reasoning" fields
- Output MUST be valid JSON (no markdown, no explanations)"""
                },
                {"role": "user", "content": sections_json}
            ],
            temperature=0,
            max_tokens=16384
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
        
        # ✅ Dict로 래핑 (DB 스키마 호환)
        translation_data = {"sections": json.loads(translated_json)}
        
        # DB 저장
        async with AsyncSessionLocal() as db_session:
            await db_session.execute(
                text("UPDATE report_summaries SET translation = :trans::jsonb WHERE summary_id = :id"),
                {"trans": json.dumps(translation_data, ensure_ascii=False), "id": report_id}
            )
            await db_session.commit()
            logger.info(f"✅ 번역 완료: summary_id={report_id}")
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ 번역 JSON 파싱 실패: {e}")
        logger.warning("⚠️ 번역 스킵, 원본 데이터 유지")
    except Exception as e:
        logger.error(f"❌ 번역 실패: {e}")
        logger.warning("⚠️ 번역 스킵, 원본 데이터 유지")
    
    return state


__all__ = ["translate_report_node"]

