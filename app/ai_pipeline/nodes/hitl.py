# app/ai_pipeline/nodes/hitl.py
"""
HITL(Human-In-The-Loop) 통합 노드

기능:
1) intent(hitl/general) 분류
2) target_node 식별
3) 피드백 정제
4) state 패치(hitl_target_node, hitl_feedback_text)
5) validator_node 호출 → 재시작 노드 결정
6) LangGraph 내 report 이후에 위치하는 hitl 노드
"""

import os
import json
import logging
import re
from typing import Dict, Any

from openai import OpenAI
from app.ai_pipeline.state import AppState

# Import prompts for refined prompt generation
from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT, MAPPING_SCHEMA
from app.ai_pipeline.prompts.strategy_prompt import STRATEGY_PROMPT, STRATEGY_SCHEMA
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT, IMPACT_SCHEMA
from app.ai_pipeline.prompts.refined_prompt import REFINED_PROMPT

logger = logging.getLogger(__name__)
client = OpenAI()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ============================================================
# 1) Intent Detection
# ============================================================

TARGET_NODE_PROMPT = """
당신은 REMON의 HITL target_node 분류기입니다.

사용자 메시지에서 수정하려는 파이프라인 단계를 식별하십시오:

- change_detection: 변경 감지 관련
- map_products: 제품 매핑 관련  
- generate_strategy: 전략 생성 관련
- score_impact: 영향도 점수 관련

출력(JSON):
{
  "target_node": "change_detection" | "map_products" | "generate_strategy" | "score_impact"
}
"""

def detect_target_node(message: str) -> str:
    """사용자 메시지 → target_node"""
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": TARGET_NODE_PROMPT},
            {"role": "user", "content": message},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
        return result.get("target_node", "map_products")
    except Exception:
        return "map_products"


# ============================================================
# 2) Feedback Cleaning
# ============================================================

CHANGE_FEEDBACK_PROMPT = """
사용자의 메시지가 의미하는 변경 감지 결과를 판단하십시오.

반드시 아래 JSON 형식으로만 답하십시오:

{ "manual_change": true }   ← 변경 있음으로 처리
또는
{ "manual_change": false }  ← 변경 없음으로 처리
"""

IMPACT_LEVEL_FEEDBACK_PROMPT = """
사용자의 피드백을 분석해서 원하는 영향도 레벨을 판단하십시오.

사용자가 원하는 것:
- 낮추고 싶다면: Low
- 높이고 싶다면: High  
- 보통/적당히/조금만 수정하고 싶다면: Medium

반드시 아래 JSON 형식으로만 답하십시오:

{ "desired_level": "Low" | "Medium" | "High" }
"""

STRATEGY_STYLE_FEEDBACK_PROMPT = """
사용자의 피드백을 분석해서 원하는 전략 스타일을 판단하십시오.

사용자가 원하는 것:
- 보수적/안전하게/신중하게: conservative
- 적극적/공격적/빠르게: aggressive
- 단계적/점진적/차근차근: gradual
- 간단하게/핵심만/최소한: minimal
- 자세하게/많이/구체적으로: detailed

반드시 아래 JSON 형식으로만 답하십시오:

{ "strategy_style": "conservative" | "aggressive" | "gradual" | "minimal" | "detailed" | "default" }
"""

def refine_hitl_feedback(message: str, target_node: str) -> str:
    """
    노드 타입에 따라 피드백 정제

    - change_detection: "true" / "false" 문자열로 정제
    - score_impact: "Low" / "Medium" / "High" 레벨로 정제
    - 나머지 노드: 자연어 피드백 한 문장 그대로 사용
    """

    if target_node == "change_detection":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": CHANGE_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            flag = bool(data.get("manual_change", False))
            return "true" if flag else "false"
        except Exception:
            return "false"
    
    elif target_node == "score_impact":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": IMPACT_LEVEL_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            return data.get("desired_level", "Medium")
        except Exception:
            return "Medium"
    
    elif target_node == "generate_strategy":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": STRATEGY_STYLE_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            return data.get("strategy_style", "default")
        except Exception:
            return "default"

    # map_products → 그냥 자연어 사용
    return message.strip()


# ============================================================
# 3) Apply HITL → Patch State + call validator
# ============================================================

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
        # score_impact 전용: 숫자 출력 강제
        error_summary += "\n\nCRITICAL REQUIREMENT: All score values MUST be plain NUMBERS (1-5), NOT objects or nested structures.\n" + \
                        "CORRECT: 'directness': 3, 'legal_severity': 4\n" + \
                        "WRONG: 'directness': {'score': 3}, 'directness': {'value': 3, 'reason': '...'}\n" + \
                        "OUTPUT ONLY FLAT JSON with number values. NO nested objects allowed."
    else:
        logger.error(f"[HITL] Unknown node for refinement: {node_name}")
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
        logger.error(f"[HITL] Failed to generate refined prompt: {e}")
        return None


def apply_hitl_patch(state: AppState, target_node: str, cleaned_feedback: str) -> AppState:
    """
    HITL 피드백을 독립적으로 처리 (validator 의존성 제거)
    """
    
    logger.info(f"[HITL] Processing feedback for {target_node}: {cleaned_feedback}")
    
    compiled_input = {
        "mapping": state.get("mapping"),
        "strategies": state.get("strategies"),  # List[str] 형태 유지
        "impact": state.get("impact_scores"),
        "regulation": state.get("regulation"),
    }
    
    # ===============================
    # change_detection 전용 HITL
    # ===============================
    if target_node == "change_detection":
        # 문자열("true"/"false") 처리
        if isinstance(cleaned_feedback, str):
            cleaned = cleaned_feedback.strip().lower()
            manual_flag = cleaned == "true"
        else:
            manual_flag = bool(cleaned_feedback)

        state["manual_change_flag"] = manual_flag
        state["needs_embedding"] = manual_flag

        logger.info(
            f"[HITL][change_detection] "
            f"manual_change_flag set to {manual_flag}, needs_embedding={manual_flag}"
        )

        if not manual_flag:  # 변경 없음일 때 - change_detection.py와 동일한 로직
            # change_detection.py와 동일한 "변경 없음" 상태 설정
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "manual_no_change",
                "total_changes": 0,
                "high_confidence_changes": 0,
                "total_reference_blocks": 0,
            }
            state["change_detection_index"] = {}
            state["regulation_analysis_hints"] = {}
            
            logger.info("[HITL][change_detection] 변경 없음 상태 직접 설정 완료 (재실행 불필요)")
            # 재실행 불필요 - 이미 완료된 상태로 설정
        else:
            # 변경 있음일 때만 초기화 후 재실행
            for key in [
                "change_detection_results",
                "change_summary",
                "regulation_analysis_hints",
                "change_detection_index",
            ]:
                if key in state:
                    state[key] = None

            state["restarted_node"] = "change_detection"
            logger.info("[HITL][change_detection] 변경 있음 - 재실행 설정")
        
    # ===============================
    # 나머지 노드들 HITL
    # ===============================
    else:
        # 모든 노드에 대해 refined prompt 생성
        if target_node == "score_impact":
            desired_level = cleaned_feedback
            error_summary = f"CRITICAL INSTRUCTION: Force impact_level to '{desired_level}' and reasoning to 'Human in the loop'.\n" + \
                           "CRITICAL: All raw_scores values must be plain numbers (1-5), not objects. Example: 'directness': 3"
            logger.info(f"[HITL] Processing score_impact feedback: {desired_level}")
        else:
            # map_products, generate_strategy는 자연어 그대로
            error_summary = f"HUMAN FEEDBACK: {cleaned_feedback}. INSTRUCTION: Adjust the analysis according to this feedback."

        # 이전 refined prompt 완전 제거 (새 HITL 피드백 반영을 위해)
        refined_key = f"refined_{target_node}_prompt"
        if refined_key in state:
            del state[refined_key]
            logger.info(f"[HITL] Removed previous refined prompt for {target_node}")
        
        # 노드별 관련 state 초기화 (누적 방지)
        if target_node == "generate_strategy":
            state["strategies"] = None  # 기존 전략 초기화
            logger.info(f"[HITL] Cleared existing strategies for regeneration")
        elif target_node == "map_products":
            state["mapping"] = None  # 기존 매핑 초기화
            state["product_info"] = None  # ⭐ 재시도 시 제품 재선택 허용
            logger.info(f"[HITL] Cleared existing mapping and product_info for regeneration")
        elif target_node == "score_impact":
            state["impact_scores"] = None  # 기존 영향도 초기화
            logger.info(f"[HITL] Cleared existing impact scores for regeneration")
        
        # refined prompt 생성 (fallback 처리 추가)
        try:
            refined_prompt = generate_refined_prompt(
                node_name=target_node,
                pipeline_state=compiled_input,
                error_summary=error_summary,
            )

            if refined_prompt:
                state[refined_key] = refined_prompt
                logger.info(f"[HITL] NEW refined prompt saved to state['{refined_key}']")
                logger.debug(f"[HITL] New refined prompt content: {refined_prompt[:200]}...")
            else:
                logger.error(f"[HITL] Failed to generate refined prompt for {target_node} → fallback accept")
        except Exception as e:
            logger.error(f"[HITL] Refined prompt generation error for {target_node}: {e} → fallback accept")

        # 재시작 노드 설정
        state["restarted_node"] = target_node
        logger.info(f"[HITL] Set restart node to: {target_node}")
    
    # HITL 메타데이터 초기화
    state["hitl_target_node"] = None
    state["hitl_feedback_text"] = None
    state.pop("hitl_feedback", None)
    
    return state


# ============================================================
# 4) LangGraph HITL 노드 (report 이후)
# ============================================================

def hitl_node(state: AppState) -> AppState:
    """
    LangGraph에서 report 이후 호출되는 HITL 노드.

    - 외부에서 사용자 피드백을 state["external_hitl_feedback"]에 넣어 준다고 가정
    - 모든 입력을 HITL 피드백으로 처리 (general 분류 제거)
    - target_node 식별 + 피드백 정제 + state 패치까지 수행
    - 이후 validator_node가 HITL 모드로 실행되며 restarted_node를 결정
    """

    user_msg = state.get("external_hitl_feedback")

    if not user_msg:
        logger.info("[HITL Node] external_hitl_feedback 없음 → 아무 것도 하지 않고 종료")
        return state

    logger.info(f"[HITL Node] 사용자 피드백 수신: {user_msg}")

    # 🔹 피드백 처리 후 즉시 제거 (무한 루프 방지)
    state["external_hitl_feedback"] = None
    logger.debug(f"[HITL] Cleared external_hitl_feedback after processing: {user_msg}")

    # (1) target_node 식별
    target = detect_target_node(user_msg)
    logger.info(f"[HITL Target] target_node = {target}")

    # (2) 피드백 정제
    cleaned = refine_hitl_feedback(user_msg, target)

    # (3) state 패치 (독립적 처리)
    new_state = apply_hitl_patch(state, target, cleaned)

    logger.info(f"[HITL Node] 처리 완료 → restarted_node={new_state.get('restarted_node')}")
    return new_state
