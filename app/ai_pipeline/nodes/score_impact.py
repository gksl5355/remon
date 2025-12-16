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
    
    # 🔥 HITL 명시적 메타데이터 우선 처리
    hitl_desired_level = state.get("hitl_desired_impact_level")
    
    if hitl_desired_level:
        # 🎯 HITL 강제 레벨 적용
        impact_level = hitl_desired_level
        
        # 점수 매핑
        level_score_map = {
            "Low": 2.0,
            "Medium": 3.0,
            "High": 4.5
        }
        weighted_score = level_score_map.get(impact_level, weighted_score)
        
        logger.info(f"[Impact] 🎯 HITL 강제 적용: {impact_level} (score={weighted_score})")
        
        # 사용 후 제거 (다음 실행 시 간섭 방지)
        state["hitl_desired_impact_level"] = None
    else:
        # 기본 로직
        impact_level = (
            "High" if weighted_score >= 4 else
            "Medium" if weighted_score >= 2.5 else
            "Low"
        )
        logger.debug(f"[Impact] 기본 로직 적용: {impact_level} (score={weighted_score:.2f})")

    # -----------------------------
    # 결과 생성 (HITL 근거 처리)
    # -----------------------------
    # HITL에서 근거를 'Human in the loop'으로 대체
    if hitl_desired_level:
        reasoning = "Human in the loop"
        logger.info("[Impact] HITL override: reasoning set to 'Human in the loop'")
    
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
    
    # HITL 적용 여부 로그
    if state.get("refined_score_impact_prompt"):
        logger.info("[Impact] ✅ HITL refined prompt applied successfully")

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
