'''
# Input State
state.regulation: dict        # 규제 정보
state.mapped_products: list   # 영향받는 제품 리스트
state.strategy: dict          # 대응 전략

# Output State
state.impact_score: dict      # 규제 영향 점수 결과
'''
import json
import os
import httpx
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

from langsmith import Client
from langsmith.run_helpers import trace


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

client_openai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=httpx.Client()
)


# ------------------------------------------
# Utility: months_left 자동 계산
# ------------------------------------------
def calculate_months_left(effective_date: str, analysis_date: str):
    try:
        ed = datetime.strptime(effective_date, "%Y-%m-%d").date()
        ad = datetime.strptime(analysis_date, "%Y-%m-%d").date()
        days = (ed - ad).days
        months = round(days / 30, 2)
        return max(months, 0)
    except:
        return None


# ============================================================
#  SCORE IMPACT (LangSmith 트레이싱 적용)
# ============================================================
def score_impact(state):

    with trace(
        name="score_impact",
        inputs={"regulation": state.regulation, "products": state.mapped_products},
        tags=["remon", "impact_scoring"]
    ) as run:

        regulation = state.regulation
        mapped_products = state.mapped_products
        strategy = state.strategy

        regulation_text = regulation.get("text", "")
        effective_date = regulation.get("effective_date")
        strategy_text = strategy.get("text", "")

        # 분석일 = 오늘 날짜
        analysis_date = datetime.today().strftime("%Y-%m-%d")

        # months_left 자동 계산
        months_left = calculate_months_left(effective_date, analysis_date)

        # -------------------------
        # LLM Prompt (너의 평가체계 100% 반영)
        # -------------------------
        prompt = f"""
    You are a senior regulatory impact analyst specializing in nicotine, tobacco, 
    public health regulations, and product compliance. Your role is to evaluate the 
    business, legal, and operational impact of regulatory changes using a 
    standardized 6-factor scoring system with fixed criteria and weights.

    Your assessment MUST strictly follow the scoring framework below.

    ====================================================================
    1. SCORING FRAMEWORK (6 FACTORS)
    ====================================================================

    ------------------------------------------------------------
    ① DIRECTNESS (0 or 1) — Weight 0.20
    ------------------------------------------------------------
    Definition:
    Whether the regulation directly impacts product formulation, ingredients, 
    manufacturing process, packaging, labeling, or distribution.

    Scoring:
    - 1 = Direct impact (ingredients, nicotine levels, packaging label changes,
        mandatory redesign, mandatory manufacturing/process changes)
    - 0 = Indirect or advisory impact


    ------------------------------------------------------------
    ② LEGAL SEVERITY (1 to 5) — Weight 0.25
    ------------------------------------------------------------
    Definition:
    Strength of legal enforcement and consequence for non-compliance.

    1 = Advisory / voluntary guidance  
    2 = Administrative guidance / recommendatory  
    3 = Reporting obligations / periodic supervision  
    4 = Fines, suspensions, mandatory corrective actions  
    5 = Sales ban, product removal, criminal penalties  


    ------------------------------------------------------------
    ③ SCOPE (1 to 5) — Weight 0.20
    ------------------------------------------------------------
    Definition:
    Commercial exposure based on the share of total sales affected.

    Scoring:
    1 = 0–10%  
    2 = 10–30%  
    3 = 30–50%  
    4 = 50–70%  
    5 = 70%+  

    Interpretation:
    - High sales_amount products strongly increase scope.
    - Multiple high-selling SKUs → higher score.


    ------------------------------------------------------------
    ④ REGULATORY URGENCY (1 to 5) — Weight 0.10
    ------------------------------------------------------------
    Definition:
    Time remaining until enforcement (months_left).

    Scoring:
    1 = ≥ 12 months  
    2 = 6–12 months  
    3 = 3–6 months  
    4 = 1–3 months  
    5 = ≤ 1 month or immediate enforcement  


    ------------------------------------------------------------
    ⑤ OPERATIONAL URGENCY (1 to 5) — Weight 0.10
    ------------------------------------------------------------
    Definition:
    Operational burden required for compliance.

    1 = Document/edit change  
    2 = Internal approval  
    3 = Multi-department coordination  
    4 = External approval or workflow restructuring  
    5 = Manufacturing changes or equipment investment  


    ------------------------------------------------------------
    ⑥ RESPONSE COST (1 to 5) — Weight 0.20
    ------------------------------------------------------------
    Definition:
    Estimated cost of compliance (labor, redesign, CAPEX, reformulation).

    1 = Administrative work  
    2 = Minor internal workload  
    3 = Packaging/design revision  
    4 = External vendor or process adjustments  
    5 = CAPEX investment or new production line  

    ====================================================================
    INPUT INFORMATION
    ====================================================================
    REGULATION TEXT:
    {regulation_text}

    EFFECTIVE DATE: {effective_date}
    ANALYSIS DATE: {analysis_date}
    MONTHS LEFT: {months_left}

    AFFECTED PRODUCTS:
    {json.dumps(mapped_products, indent=2, ensure_ascii=False)}

    STRATEGY:
    {strategy_text}

    ====================================================================
    OUTPUT JSON ONLY
    ====================================================================
    Return ONLY this JSON:

    {{
    "directness": 0,
    "legal_severity": 0,
    "scope": 0,
    "regulatory_urgency": 0,
    "operational_urgency": 0,
    "response_cost": 0,
    "reasoning": "..."
    }}
    """

        response = client_openai.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "Respond ONLY with valid JSON. No markdown. No commentary."
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=800
        )

        raw = response.choices[0].message.content
        scores = json.loads(raw)

        # -------------------------
        # WEIGHTED SCORE
        # -------------------------
        weights = {
            "directness": 0.20,
            "legal_severity": 0.25,
            "scope": 0.20,
            "regulatory_urgency": 0.10,
            "operational_urgency": 0.10,
            "response_cost": 0.20,
        }

        weighted_score = sum(scores[k] * weights[k] for k in weights)

        impact_level = (
            "High" if weighted_score >= 4 else
            "Medium" if weighted_score >= 2.5 else
            "Low"
        )

        state.impact_score = {
            "raw_scores": scores,
            "weighted_score": round(weighted_score, 2),
            "impact_level": impact_level
        }

        run.outputs = {"impact_score": state.impact_score}

    return state
