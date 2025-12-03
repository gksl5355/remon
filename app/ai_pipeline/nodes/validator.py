# app/ai_pipeline/nodes/validator.py

import logging
import json
import re
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()


# ------------------------------------------------------------
# 1) Node별 원본 프롬프트 및 스키마 로드
# ------------------------------------------------------------
from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT, MAPPING_SCHEMA
from app.ai_pipeline.prompts.strategy_prompt import STRATEGY_PROMPT, STRATEGY_SCHEMA
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT, IMPACT_SCHEMA

# Global validator prompt 
from app.ai_pipeline.prompts.validator_prompt import VALIDATOR_PROMPT
from app.ai_pipeline.prompts.refined_prompt import REFINED_PROMPT

# ------------------------------------------------------------
# Refined Prompt Generator
# ------------------------------------------------------------
def generate_refined_prompt(node_name: str, pipeline_state: dict, error_summary: str):
    """Generate a refined version of the original prompt for a specific node."""

    if node_name == "map_products":
        original_prompt = MAPPING_PROMPT
        schema = MAPPING_SCHEMA
    elif node_name == "generate_strategy":
        original_prompt = STRATEGY_PROMPT
        schema = STRATEGY_SCHEMA
    elif node_name == "score_impact":
        original_prompt = IMPACT_PROMPT
        schema = IMPACT_SCHEMA
    else:
        logger.error(f"[Validator] Unknown node for refinement: {node_name}")
        return None

    refine_request = REFINED_PROMPT.format(
        original_prompt=original_prompt.strip(),
        error_summary=error_summary,
        pipeline_state=json.dumps(pipeline_state, ensure_ascii=False, indent=2),
        schema=json.dumps(schema, ensure_ascii=False, indent=2),
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You rewrite prompts to be strict and error-proof."},
                {"role": "user", "content": refine_request},
            ],
            temperature=0,
        )
        refined_prompt_text = resp.choices[0].message.content.strip()
        return refined_prompt_text

    except Exception as e:
        logger.error(f"[Validator] Failed to generate refined prompt: {e}")
        return None


# ------------------------------------------------------------
# Main Validator Node
# ------------------------------------------------------------
def validator_node(state):
    logger.info("[Validator] Running Global Validation…")

    retry_count = state.get("validation_retry_count", 0) or 0
    state["validation_retry_count"] = retry_count + 1

    # Retry 제한: 1회
    if retry_count >= 1:
        logger.warning("[Validator] Retry limit reached → accepting result.")
        return {
            "validation_result": {"is_valid": True, "restart_node": None},
            "restarted_node": None,
        }

    # -----------------------------
    # 검증 입력 데이터 준비
    # -----------------------------
    compiled_input = {
        "mapping": state.get("mapping"),
        "strategy": state.get("strategies"),
        "impact": state.get("impact_scores"),
        "regulation": state.get("regulation"),
    }

    payload = json.dumps(compiled_input, ensure_ascii=False, indent=2)

    # -----------------------------
    # LLM Validator 실행
    # -----------------------------
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        raw_clean = raw.replace("```json", "").replace("```", "")

        match = re.search(r"\{.*\}", raw_clean, re.DOTALL)
        decision = json.loads(match.group(0)) if match else json.loads(raw_clean)

    except Exception as e:
        logger.error(f"[Validator] Parsing error → fallback accept: {e}")
        return {
            "validation_result": {"is_valid": True, "restart_node": None},
            "restarted_node": None,
        }

    restart_node = decision.get("restart_node")
    error_summary = decision.get("reason", "")

    # -----------------------------
    # Valid → Pass
    # -----------------------------
    if not restart_node:
        return {
            "validation_result": decision,
            "restarted_node": None,
        }

    logger.warning(f"[Validator] Restarting node: {restart_node}")

    # -----------------------------
    # Refined prompt 생성
    # -----------------------------
    refined_prompt = generate_refined_prompt(
        node_name=restart_node,
        pipeline_state=compiled_input,
        error_summary=error_summary,
    )

    if refined_prompt:
        state[f"refined_{restart_node}_prompt"] = refined_prompt
        logger.info(f"[Validator] Refined prompt saved to state['refined_{restart_node}_prompt']")

    # -----------------------------
    # 문제 발생 노드 초기화
    # -----------------------------
    if restart_node == "map_products":
        state["mapping"] = None

    elif restart_node == "generate_strategy":
        state["strategies"] = None

    elif restart_node == "score_impact":
        state["impact_scores"] = None

    return {
        **state,
        "validation_result": decision,
        "restarted_node": restart_node,
    }
