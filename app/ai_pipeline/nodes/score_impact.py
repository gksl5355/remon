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
    strategy: StrategyResults | None = state.get("strategy")
    strategies_list = state.get("strategies")

    # 전략 형태 보정
    if strategy is None and strategies_list:
        strategy = {"items": [{"summary": s} for s in strategies_list]}

    # 매핑/전략 없으면 스킵
    if not mapping or not strategy:
        logger.warning("[Impact] Skip: mapping or strategy missing")
        return state

    logger.info("[Impact] Starting impact scoring...")
    logger.debug("[Impact] Mapping items: %s", mapping.get("items"))
    logger.debug("[Impact] Strategy items: %s", strategy.get("items"))

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

    strategy_text = " ".join(
        s.get("summary", "") for s in strategy.get("items", [])
    ).strip()

    # -----------------------------
    # 프롬프트 생성 + 로그
    # -----------------------------

    # refined prompt 우선 적용
    if state.get("refined_score_impact_prompt"):
        prompt = state["refined_score_impact_prompt"]
        logger.info("[Impact] Using REFINED IMPACT PROMPT from validator")
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
    
    # HITL refined prompt에서 강제 레벨 지정이 있는지 확인
    if state.get("refined_score_impact_prompt"):
        refined_prompt = state["refined_score_impact_prompt"]
        if "LOW impact level" in refined_prompt or "impact_level to 'Low'" in refined_prompt:
            impact_level = "Low"
            weighted_score = min(weighted_score, 2.4)  # Low 레벨 보장
        elif "HIGH impact level" in refined_prompt or "impact_level to 'High'" in refined_prompt:
            impact_level = "High"
            weighted_score = max(weighted_score, 4.1)  # High 레벨 보장
        elif "MEDIUM impact level" in refined_prompt or "impact_level to 'Medium'" in refined_prompt:
            impact_level = "Medium"
            weighted_score = max(2.5, min(weighted_score, 3.9))  # Medium 레벨 보장
        else:
            # 기본 로직
            impact_level = (
                "High" if weighted_score >= 4 else
                "Medium" if weighted_score >= 2.5 else
                "Low"
            )
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
    if state.get("refined_score_impact_prompt") and "reasoning to 'Human in the loop'" in state["refined_score_impact_prompt"]:
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

    # refined prompt 제거
    if state.get("refined_score_impact_prompt"):
        state["refined_score_impact_prompt"] = None

    return state
