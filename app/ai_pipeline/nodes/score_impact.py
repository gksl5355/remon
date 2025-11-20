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
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT_TEMPLATE


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
    # 전략은 두 가지 형태를 지원: {"items": [...]} 또는 단순 리스트(state["strategies"])
    strategy: StrategyResults | None = state.get("strategy")
    strategies_list = state.get("strategies")
    if strategy is None and strategies_list:
        strategy = {"items": [{"summary": s} for s in strategies_list]}

    # 매핑/전략 없으면 스킵
    if not mapping or not strategy:
        return state

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

    # -----------------------------
    # 제품 매핑 정보 JSON 변환
    # -----------------------------
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
    # 프롬프트 생성
    # -----------------------------
    prompt = IMPACT_PROMPT_TEMPLATE.format(
        regulation_text=regulation_text,
        products_json=json.dumps(products_json_list, ensure_ascii=False, indent=2),
        strategy_text=strategy_text,
        months_left=months_left,
    )

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
        llm_out = json.loads(response.choices[0].message.content)

    except Exception as e:
        print("[ERROR] Impact scoring LLM parsing failed:", e)
        return state

    # -----------------------------
    # 점수 분리
    # -----------------------------
    reasoning = llm_out.pop("reasoning", "")
    raw_scores = llm_out   # 나머지는 전부 점수로 간주

    # -----------------------------
    # 가중합 계산
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

    impact_level = (
        "High" if weighted_score >= 4 else
        "Medium" if weighted_score >= 2.5 else
        "Low"
    )

    # -----------------------------
    # ImpactScoreItem 생성
    # -----------------------------
    impact_item: ImpactScoreItem = {
        "raw_scores": raw_scores,
        "weighted_score": round(weighted_score, 2),
        "impact_level": impact_level,
        "reasoning": reasoning,
    }

    # -----------------------------
    # State 업데이트
    # -----------------------------
    state.setdefault("impact_scores", [])
    state["impact_scores"].append(impact_item)

    return state
