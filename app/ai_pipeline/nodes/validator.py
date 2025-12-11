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

# HITL(hitl_target_node, hitl_feedback_text)
from app.ai_pipeline.state import AppState

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
                {
                    "role": "system",
                    "content": "You rewrite prompts to be strict and error-proof.",
                },
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

    compiled_input = {
        "mapping": state.get("mapping"),
        "strategy": state.get("strategies"),
        "impact": state.get("impact_scores"),
        "regulation": state.get("regulation"),
    }

    # ------------------------------------------------
    # [HITL] Human-in-the-Loop 분기
    # ------------------------------------------------
    hitl_target_node = state.get("hitl_target_node")
    hitl_feedback_text = state.get("hitl_feedback_text")

    if hitl_target_node and hitl_feedback_text:

        state["validation_retry_count"] = 0 #hitl마다 초기화

        logger.warning(
            f"[Validator][HITL] Human feedback override detected → "
            f"target_node={hitl_target_node}"
        )

        # ===============================
        # 2-1) detect_changes 전용 HITL
        # ===============================
        if hitl_target_node == "detect_changes":
            # clean_hitl_feedback 에서 이미 "true"/"false"로 정제돼 있다고 가정
            cleaned = str(hitl_feedback_text).strip().lower()
            manual_flag = cleaned == "true"

            state["manual_change_flag"] = manual_flag

            # HITL 변경 감지 == 결과 강제
            if manual_flag:
                # 변경 있음 → Embedding 필요
                state["needs_embedding"] = True
            else:
                # 변경 없음 → Embedding 불필요
                state["needs_embedding"] = False
            logger.warning(
                f"[Validator][HITL][detect_changes] "
                f"manual_change_flag set to {manual_flag}"
            )

            # 변경 감지 이후에 의존하는 결과들 초기화
            for key in [
                "detect_changes_results",
                "change_summary",
                "regulation_analysis_hints",
                "detect_changes_index",
                "mapping",
                "strategies",
                "impact_scores",
                "report",
            ]:
                if key in state:
                    state[key] = None

            # HITL 메타데이터 초기화
            state["hitl_target_node"] = None
            state["hitl_feedback_text"] = None

            validation_result = {
                "is_valid": False,
                "restart_node": "detect_changes",
                "reason": "hitl_override_detect_changes",
                "source": "hitl",
            }

            return {
                **state,
                "validation_result": validation_result,
                "restarted_node": "detect_changes",
            }

        # ===============================
        # 2-2) 나머지 노드(map/strategy/impact) HITL
        # ===============================
        restart_node = hitl_target_node
        error_summary = hitl_feedback_text  # 사람 피드백을 그대로 error_summary로 사용

        refined_prompt = generate_refined_prompt(
            node_name=restart_node,
            pipeline_state=compiled_input,
            error_summary=error_summary,
        )

        if refined_prompt:
            state[f"refined_{restart_node}_prompt"] = refined_prompt
            logger.info(
                f"[Validator][HITL] Refined prompt saved to "
                f"state['refined_{restart_node}_prompt']"
            )

        # 문제 발생 노드 초기화
        if restart_node == "map_products":
            state["mapping"] = None
        elif restart_node == "generate_strategy":
            state["strategies"] = None
        elif restart_node == "score_impact":
            state["impact_scores"] = None

        state["hitl_target_node"] = None
        state["hitl_feedback_text"] = None

        validation_result = {
            "is_valid": False,
            "restart_node": restart_node,
            "reason": "hitl_override",
            "source": "hitl",
        }

        return {
            **state,
            "validation_result": validation_result,
            "restarted_node": restart_node,
        }

    # Retry 제한: 1회 (자동 Validator 경로에만 적용)
    if retry_count >= 1:
        logger.warning("[Validator] Retry limit reached → accepting result.")
        return {
            "validation_result": {"is_valid": True, "restart_node": None},
            "restarted_node": None,
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
        logger.info(
            f"[Validator] Refined prompt saved to state['refined_{restart_node}_prompt']"
        )

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
