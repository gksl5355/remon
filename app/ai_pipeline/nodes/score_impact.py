"""
score_impact.py
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import httpx

from openai import OpenAI
from typing import Any, Dict, List

from app.ai_pipeline.state import (
    AppState,
    MappingResults,
    StrategyResults,
    ImpactScoreItem,
)
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT

import logging

logger = logging.getLogger(__name__)

# -----------------------------------------------------
# ENV & OpenAI Client
# -----------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

client_openai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=httpx.Client(trust_env=False)
)


# -----------------------------------------------------
# Utility: months_left 계산
# -----------------------------------------------------
def calculate_months_left(effective_date: str, analysis_date: str):
    if not effective_date:
        return None

    try:
        ed = datetime.strptime(effective_date, "%Y-%m-%d").date()
        ad = datetime.strptime(analysis_date, "%Y-%m-%d").date()
        days = (ed - ad).days
        months = round(days / 30, 2)
        return max(months, 0)
    except Exception:
        return None


# -----------------------------------------------------
# LangGraph Node
# -----------------------------------------------------

async def score_impact_node(state: AppState) -> AppState:

    regulation = state.get("regulation", {})
    mapping: MappingResults | None = state.get("mapping")
    strategies_list = state.get("strategies", [])

    # 매핑/전략 없으면 스킵
    if not mapping or not strategies_list:
        logger.warning("[Impact] Skip: mapping or strategies missing")
        return state

    logger.info("[Impact] Starting impact scoring...")
    logger.debug("[Impact] Mapping items: %s", mapping.get("items"))
    logger.debug("[Impact] Strategy items: %s", strategies_list)

    # -----------------------------
    # INPUT 전처리
    # -----------------------------
    regulation_text = (
        regulation.get("text")
        or (mapping.get("items") or [{}])[0].get("regulation_summary")
        or ""
    )

    effective_date = regulation.get("effective_date")
    analysis_date = datetime.today().strftime("%Y-%m-%d")
    months_left = calculate_months_left(effective_date, analysis_date)

    # 제품 매핑 JSON 구성
    products_json_list = []
    for item in mapping["items"]:
        products_json_list.append({
            "product_id": item.get("product_id"),
            "feature_name": item.get("feature_name"),
            "current_value": item.get("current_value"),
            "required_value": item.get("required_value"),
            "gap": item.get("gap"),
        })

    # ✅ CoT 구조 전략 처리
    if strategies_list and isinstance(strategies_list[0], dict):
        # CoT 구조: recommended_strategy만 추출
        strategy_text = " ".join([s.get("recommended_strategy", "") for s in strategies_list if s.get("recommended_strategy")]).strip()
    else:
        # Legacy 구조: 문자열 리스트
        strategy_text = " ".join(strategies_list).strip()

    # -----------------------------
    # 프롬프트 생성 + 로그
    # -----------------------------

    # refined prompt 우선 적용
    if state.get("refined_score_impact_prompt"):
        prompt = state["refined_score_impact_prompt"]
        logger.info("[Impact] Using REFINED IMPACT PROMPT from validator")
        logger.debug(f"[Impact] Refined prompt content: {prompt[:200]}...")  # 디버깅용
    else:
        prompt = IMPACT_PROMPT.format(
            regulation_text=regulation_text,
            products_json=json.dumps(products_json_list, ensure_ascii=False, indent=2),
            strategy_text=strategy_text,
            months_left=months_left,
        )

    logger.debug("\n\n[Impact Prompt]\n%s\n", prompt)

    # -----------------------------
    # LLM 호출
    # -----------------------------
    try:
        response = client_openai.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw_llm_output = response.choices[0].message.content
        logger.debug("\n[Impact Raw LLM Output]\n%s\n", raw_llm_output)

        llm_out = json.loads(raw_llm_output)

    except Exception as e:
        logger.error("[Impact] LLM JSON parsing failed: %s", e)
        return state

    # -----------------------------
    # 점수 분리
    # -----------------------------
    reasoning = llm_out.pop("reasoning", "")
    raw_scores = llm_out

    logger.debug("[Impact] Raw score dict: %s", raw_scores)

    # 🔧 LLM이 dict로 반환한 경우 숫자 추출
    for key, value in list(raw_scores.items()):
        if isinstance(value, dict):
            # 스키마 반환 감지 (type/description 필드)
            if 'type' in value and 'description' in value:
                logger.error(f"[Impact] {key} is schema, not score! Skipping...")
                raw_scores[key] = 0
            else:
                raw_scores[key] = value.get('score') or value.get('value') or 0
                logger.warning(f"[Impact] {key} was dict, extracted: {raw_scores[key]}")

    # -----------------------------
    # 가중합 계산 및 HITL 강제 레벨 적용
    # -----------------------------
    weights = {
        "directness": 0.20,
        "legal_severity": 0.25,
        "scope": 0.20,
        "regulatory_urgency": 0.10,
        "operational_urgency": 0.10,
        "response_cost": 0.20,
    }

    weighted_score = sum(raw_scores.get(k, 0) * w for k, w in weights.items())
    
    # HITL refined prompt에서 강제 레벨 지정이 있는지 확인
    if state.get("refined_score_impact_prompt"):
        refined_prompt = state["refined_score_impact_prompt"]
        
        # 정확한 매칭을 위해 순서 변경 (HIGH → MEDIUM → LOW)
        if "Force impact_level to 'High'" in refined_prompt or "FORCE IMPACT_LEVEL TO 'HIGH'" in refined_prompt.upper():
            impact_level = "High"
            weighted_score = 4.5
            logger.info("[Impact] ✅ HITL override: Force High level (4.5)")
        elif "Force impact_level to 'Medium'" in refined_prompt or "FORCE IMPACT_LEVEL TO 'MEDIUM'" in refined_prompt.upper():
            impact_level = "Medium"
            weighted_score = 3.0
            logger.info("[Impact] ✅ HITL override: Force Medium level (3.0)")
        elif "Force impact_level to 'Low'" in refined_prompt or "FORCE IMPACT_LEVEL TO 'LOW'" in refined_prompt.upper():
            impact_level = "Low"
            weighted_score = 2.0
            logger.info("[Impact] ✅ HITL override: Force Low level (2.0)")
        else:
            # 기본 로직
            impact_level = (
                "High" if weighted_score >= 4 else
                "Medium" if weighted_score >= 2.5 else
                "Low"
            )
            logger.warning(f"[Impact] ⚠️ HITL prompt 감지 실패, 기본 로직 사용: {refined_prompt[:100]}...")
    else:
        # 기본 로직
        impact_level = (
            "High" if weighted_score >= 4 else
            "Medium" if weighted_score >= 2.5 else
            "Low"
        )

    # -----------------------------
    # 결과 생성 (HITL 근거 처리)
    # -----------------------------
    # HITL에서 근거를 'Human in the loop'으로 대체
    if state.get("refined_score_impact_prompt"):
        if "reasoning to 'Human in the loop'" in state["refined_score_impact_prompt"]:
            reasoning = "Human in the loop"
            logger.info("[Impact] ✅ HITL override: reasoning set to 'Human in the loop'")
    elif isinstance(reasoning, dict):
        # 스키마 반환 감지
        logger.error(f"[Impact] reasoning is schema: {reasoning}")
        reasoning = "LLM returned schema instead of reasoning"
    
    impact_item: ImpactScoreItem = {
        "raw_scores": raw_scores,
        "weighted_score": round(weighted_score, 2),
        "impact_level": impact_level,
        "reasoning": reasoning,
    }

    # HITL 재실행 시 기존 결과 교체
    state["impact_scores"] = [impact_item]

    logger.info("[Impact] Final Impact Score: %s (Level: %s, Score: %.2f)", 
                impact_item, impact_level, weighted_score)
    
    # refined prompt 제거 (재실행 방지)
    if state.get("refined_score_impact_prompt"):
        state["refined_score_impact_prompt"] = None
        logger.info("[Impact] ✅ HITL refined prompt 적용 완료 (제거됨)")

    # 🆕 중간 결과물 저장 (HITL용)
    regulation_id = None
    regulation = state.get("regulation", {})
    if regulation:
        regulation_id = regulation.get("regulation_id")
    
    if not regulation_id:
        preprocess_results = state.get("preprocess_results", [])
        if preprocess_results:
            regulation_id = preprocess_results[0].get("regulation_id")
    
    if regulation_id and state.get("impact_scores"):
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        from app.core.database import AsyncSessionLocal
        
        logger.info(f"💾 영향도 중간 결과물 저장 시작: regulation_id={regulation_id}")
        
        async with AsyncSessionLocal() as session:
            intermediate_repo = IntermediateOutputRepository()
            try:
                intermediate_data = {
                    "impact_scores": state["impact_scores"],
                    "raw_scores": impact_item.get("raw_scores"),
                    "weighted_score": impact_item.get("weighted_score"),
                    "impact_level": impact_item.get("impact_level"),
                    "reasoning": impact_item.get("reasoning"),
                }
                await intermediate_repo.save_intermediate(
                    session,
                    regulation_id=regulation_id,
                    node_name="score_impact",
                    data=intermediate_data
                )
                await session.commit()
                logger.info(f"✅ 영향도 중간 결과물 저장 완료: regulation_id={regulation_id}")
            except Exception as db_err:
                await session.rollback()
                logger.error(f"❌ 영향도 중간 결과물 저장 실패: {db_err}")
    else:
        logger.warning(f"⚠️ 영향도 중간 결과물 저장 스킵: regulation_id={regulation_id}")

    return state
