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
from typing import Dict, Any

from openai import OpenAI
from app.ai_pipeline.state import AppState
from app.ai_pipeline.nodes.validator import validator_node

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

def refine_hitl_feedback(message: str, target_node: str) -> str:
    """
    노드 타입에 따라 피드백 정제

    - change_detection: "true" / "false" 문자열로 정제
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
            # validator 쪽에서 "true"/"false" 문자열 기준으로 manual_change_flag 계산함
            return "true" if flag else "false"
        except Exception:
            return "false"

    # map_products / generate_strategy / score_impact → 그냥 자연어 사용
    return message.strip()


# ============================================================
# 3) Apply HITL → Patch State + call validator
# ============================================================

def apply_hitl_patch(state: AppState, target_node: str, cleaned_feedback: str) -> AppState:
    """
    HITL 피드백을 state에 반영한 뒤, validator_node를 호출한다.

    여기서는:
    - hitl_target_node
    - hitl_feedback_text

    두 가지만 세팅하고, 나머지 세부 로직(필드 초기화, manual_change_flag, refined_prompt 생성 등)은
    전부 validator_node에 맡긴다.
    """

    state["hitl_target_node"] = target_node
    state["hitl_feedback_text"] = cleaned_feedback
    state["validation_retry_count"] = 0  # HITL 들어올 때마다 retry 카운터 리셋

    # 나머지 로직은 validator가 처리
    updated_state = validator_node(state)
    return updated_state


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

    # (1) target_node 식별
    target = detect_target_node(user_msg)
    logger.info(f"[HITL Target] target_node = {target}")

    # (2) 피드백 정제
    cleaned = refine_hitl_feedback(user_msg, target)

    # (3) state 패치 + validator 호출
    new_state = apply_hitl_patch(state, target, cleaned)

    logger.info(f"[HITL Node] validator 결과 → restarted_node={new_state.get('restarted_node')}")
    return new_state
