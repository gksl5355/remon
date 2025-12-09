# app/chatbot/service.py
"""
REMON 챗봇 서비스의 최상위 오케스트레이션 레이어 (MVP 버전)

이 파일은 다음을 수행한다:

1) 사용자의 입력을 intent 분류기로 전달
2) HITL이면 hitl.py 로 전달하여 피드백 문장 정제 + state 구성
3) validator_node 로 state 전달하여 노드 재실행 트리거
4) general이면 일반 LLM 답변만 반환

즉, 이 파일은 "사용자 메시지 → 시스템 동작" 전체 흐름을 제어한다.
"""

import os
from typing import Dict, Any

from openai import OpenAI
import logging

# --- 챗봇 내부 모듈 ---
from app.ai_pipeline.nodes.chatbot.intent import detect_intent
from app.ai_pipeline.nodes.chatbot.hitl import clean_hitl_feedback, build_hitl_state

# --- AI 파이프라인 노드 ---
from app.ai_pipeline.nodes.validator import validator_node
from app.ai_pipeline.state import AppState  # 타입 힌트용 (dict처럼 사용)

logger = logging.getLogger(__name__)

# -----------------------------
# OpenAI 모델 설정 (.env에서 불러옴)
# -----------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI()


# ============================================================
# General Chat용 단순 LLM 응답 함수
# ============================================================
def llm_general_response(user_message: str) -> str:
    """
    HITL이 아닌 일반 질의에 대해 단순 LLM 응답을 반환한다.
    (REMON 파이프라인과 무관한 일반 대화, 규제 설명 등)
    """
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "당신은 친절하고 간단 명료한 챗봇입니다."},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


# ============================================================
# 챗봇 메인 엔트리포인트 (서비스 최상위)
# ============================================================
def process_chat_message(user_message: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자의 메시지를 입력받아 적절한 시스템 반응을 수행한다.

    Parameters
    ----------
    user_message : str
        사용자 입력
    state : dict (AppState 호환)
        LangGraph 파이프라인 전체 상태

    Returns
    -------
    dict
        - general 채팅:
            {
              "mode": "general",
              "reply": "<LLM 응답>",
              "state": <변경 없는 state>
            }

        - hitl 요청:
            {
              "mode": "hitl",
              "reply": "HITL 적용 완료 → <노드> 노드를 다시 실행합니다.",
              "state": <validator 실행 이후 state>
            }
    """

    # 1) intent 감지 (dict 반환: {"intent": "...", "target_node": ...})
    intent_result = detect_intent(user_message)
    intent_type = intent_result.get("intent")        # "general" 또는 "hitl"
    target_node = intent_result.get("target_node")   # map_products / generate_strategy / score_impact / None

    logger.info(f"[Chatbot] intent = {intent_result}")

    # ------------------------------------------------------------
    # CASE 1) 일반 챗봇 응답 (general)
    # ------------------------------------------------------------
    if intent_type == "general":
        reply = llm_general_response(user_message)
        return {
            "mode": "general",
            "reply": reply,
            "state": state,  # state는 그대로 유지
        }

    # ------------------------------------------------------------
    # CASE 2) HITL (노드 재실행 요청)
    # ------------------------------------------------------------
    if intent_type == "hitl":
        """
        user_message 예시:
        - "전략이 너무 단순함 → generate_strategy 다시 생성"
        - "score_impact 점수가 근거 부족 → 다시 돌려줘"
        - "이 매핑 이상해 → mapping 다시"
        """

        # a) target_node 안전성 체크
        if target_node not in {"map_products", "generate_strategy", "score_impact"}:
            return {
                "mode": "error",
                "reply": f"HITL 타깃 노드를 식별할 수 없습니다: {target_node}",
                "state": state,
            }

        # b) 사용자 피드백 문장 정제 (불필요한 말 제거, 핵심만 한 문장으로)
        cleaned_text = clean_hitl_feedback(user_message)

        # c) validator가 사용할 HITL용 state 조각 생성
        hitl_patch = build_hitl_state(target_node, cleaned_text)
        #   hitl_patch 예시:
        #   {
        #       "hitl_target_node": "generate_strategy",
        #       "hitl_feedback_text": "전략이 너무 추상적이어서 실행 불가능하므로 더 구체적으로 다시 생성 필요"
        #   }

        # d) 기존 state에 병합
        state.update(hitl_patch)

        # e) validator 실행 → 해당 노드 재실행 준비
        #    validator_node는 state를 받아서:
        #    - refined_XXX_prompt 주입
        #    - 재시작할 노드 정보(restarted_node) 설정
        #    - validation_result 업데이트
        validator_output = validator_node(state)

        return {
            "mode": "hitl",
            "reply": f"HITL 적용 완료 → {target_node} 노드를 다시 실행합니다.",
            "state": validator_output,
        }

    # ------------------------------------------------------------
    # CASE 3) 알 수 없는 intent → general fallback
    # ------------------------------------------------------------
    reply = llm_general_response(user_message)
    return {
        "mode": "general",
        "reply": reply,
        "state": state,
    }
