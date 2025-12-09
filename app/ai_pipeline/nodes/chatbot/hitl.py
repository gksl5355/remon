# app/chatbot/hitl.py
"""
Human-In-The-Loop(HITL) 피드백 처리 모듈

이 파일은 다음 역할을 수행한다:

1) 사용자가 HITL 모드에서 입력한 원본 메시지를 정제(cleaning)
2) validator_node가 이해할 수 있도록 state에 저장할 값 생성
   - hitl_target_node
   - hitl_feedback_text

즉, 이 모듈은 "사용자 → validator"로 전달하는 중간 변환 담당.
"""

import os
from openai import OpenAI

# -----------------------------
# OpenAI 모델 설정 (.env에서 로딩)
# -----------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI()


# -----------------------------
# HITL 텍스트 정제 프롬프트
# -----------------------------
HITL_CLEAN_PROMPT = """
당신은 REMON 규제 시스템의 HITL 피드백 정제기입니다.

아래 사용자의 피드백 메시지를 기반으로,
- 모호하거나 감정적인 표현을 제거하고
- 노드가 이해할 수 있도록 문제의 핵심만 깔끔한 한 문장으로 정제하십시오.

반드시 '단순 명료한 피드백 문장'만 출력하세요.
불필요한 설명은 하지 마십시오.
"""


# ============================================================
# HITL 피드백 정제 함수
# ============================================================
def clean_hitl_feedback(user_feedback: str) -> str:
    """
    HITL 피드백 문장을 정제하여 validator에 직접 넣을 수 있는 형태로 가공한다.

    Parameters
    ----------
    user_feedback : str
        사용자가 입력한 원본 HITL 메시지

    Returns
    -------
    str
        노드가 바로 사용할 수 있는 깔끔한 피드백 문장
    """
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": HITL_CLEAN_PROMPT},
            {"role": "user", "content": user_feedback},
        ],
        temperature=0
    )

    cleaned = resp.choices[0].message.content.strip()
    return cleaned


# ============================================================
# validator가 사용할 HITL용 state 값 생성 함수
# ============================================================
def build_hitl_state(target_node: str, cleaned_feedback: str) -> dict:
    """
    validator_node로 전달할 HITL 전용 state 값들을 구성한다.

    Parameters
    ----------
    target_node : str
        map_products / generate_strategy / score_impact 중 하나

    cleaned_feedback : str
        정제된 사용자 피드백 문장

    Returns
    -------
    dict
        validator_node(state)에 병합할 HITL 관련 state
        {
            "hitl_target_node": ...,
            "hitl_feedback_text": ...
        }
    """

    return {
        "hitl_target_node": target_node,
        "hitl_feedback_text": cleaned_feedback,
    }
