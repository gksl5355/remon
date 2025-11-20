"""
score_impact.py
Impact scoring node (FINAL PRODUCTION VERSION)
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

from app.ai_pipeline.state import AppState, MappingResults, StrategyResults
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT_TEMPLATE


# -----------------------------------------------------
# ENV & OpenAI Client
# -----------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# 단순화된 안전한 클라이언트 생성
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
    mapping: MappingResults = state.get("mapping")
    strategy: StrategyResults = state.get("strategy")

    if not mapping or not strategy:
        return state

    # -----------------------------------------------------
    # INPUT 구성
    # -----------------------------------------------------
    regulation_text = regulation.get("text", "")
    effective_date = regulation.get("effective_date")

    # product list 생성
    products = []
    for item in mapping["items"]:
        products.append({
            "product_id": mapping.get("product_id"),
            "feature": item.get("feature_name"),
            "sales_amount": item.get("sales_amount", 0),
        })

    # strategy summary 합치기
    strategy_text = " ".join([
        s.get("summary", "") for s in strategy.get("items", [])
    ]).strip()

    # 날짜 계산
    analysis_date = datetime.today().strftime("%Y-%m-%d")
    months_left = calculate_months_left(effective_date, analysis_date)

    # -----------------------------------------------------
    # Prompt 생성
    # -----------------------------------------------------
    prompt = IMPACT_PROMPT_TEMPLATE.format(
        regulation_text=regulation_text,
        products_json=json.dumps(products, ensure_ascii=False, indent=2),
        strategy_text=strategy_text,
        months_left=months_left,
    )

    # -----------------------------------------------------
    # LLM 호출
    # -----------------------------------------------------
    try:
        response = client_openai.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Respond ONLY with valid JSON. No comments."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content
        scores = json.loads(content)

    except Exception as e:
        # LLM 오류 발생 시 fallback
        print("[ERROR] Impact scoring LLM parsing failed:", e)
        return state

    # -----------------------------------------------------
    # 가중합 계산
    # -----------------------------------------------------
    weights = {
        "directness": 0.20,
        "legal_severity": 0.25,
        "scope": 0.20,
        "regulatory_urgency": 0.10,
        "operational_urgency": 0.10,
        "response_cost": 0.20,
    }

    weighted_score = 0
    for key, weight in weights.items():
        weighted_score += scores.get(key, 0) * weight

    impact_level = (
        "High" if weighted_score >= 4 else
        "Medium" if weighted_score >= 2.5 else
        "Low"
    )

    # -----------------------------------------------------
    # state 반영
    # -----------------------------------------------------
    if "impact_scores" not in state:
        state["impact_scores"] = []

    state["impact_scores"].append({
        "product_id": mapping.get("product_id"),
        "raw_scores": scores,
        "weighted_score": round(weighted_score, 2),
        "impact_level": impact_level,
    })

    return state
