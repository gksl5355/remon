# app/chatbot/hitl.py
"""
Human-In-The-Loop(HITL) 피드백 처리 모듈

1) 사용자가 HITL 모드에서 입력한 원본 메시지를 정제(cleaning)

   - detect_changes 노드일 경우:
       → 사용자의 표현을 분석하여 반드시 "true" 또는 "false" 문자열로 변환한다.
         (true = 변경 있음, false = 변경 없음)

   - 그 외 노드(map_products, generate_strategy, score_impact):
       → 불필요한 표현을 제거하고, 노드가 이해할 수 있는
         단일·명확한 한국어 문장으로 정제한다.

2) validator_node가 이해하고 사용할 수 있도록 HITL 관련 state 값을 구성한다.
   - hitl_target_node : 어떤 노드를 재실행해야 하는지 지정
   - hitl_feedback_text : 정제된 피드백 (detect_changes은 true/false)

즉, 이 모듈은 "사용자 → HITL 텍스트 정제 → validator로 전달되는 state 패치"
전체 흐름의 중간 변환 계층 역할을 한다.

"""

import os
from openai import OpenAI

# -----------------------------
# OpenAI 모델 설정 (.env에서 로딩)
# -----------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI()


# -----------------------------
# 공통 HITL 정제 프롬프트 (map/strategy/impact)
# -----------------------------
HITL_CLEAN_PROMPT_GENERAL = """
당신은 REMON 규제 시스템의 HITL 피드백 정제기입니다.

아래 사용자의 피드백 메시지를 기반으로,
- 모호하거나 감정적인 표현을 제거하고
- 노드가 이해할 수 있도록 문제의 핵심만 깔끔한 한 문장으로 정제하십시오.

반드시 '단순 명료한 피드백 문장'만 출력하세요.
불필요한 설명은 하지 마십시오.
"""

# ------------------------------------------
# detect_changes 전용 HITL 프롬프트 (boolean)
# ------------------------------------------
HITL_CLEAN_PROMPT_detect_changes = """
당신은 REMON 규제 시스템의 '변경 감지' HITL 피드백 정제기입니다.

사용자의 메시지는 "변경이 맞다 / 아니다" 또는 그에 준하는 내용입니다.

규칙:
- 반드시 true 또는 false 둘 중 하나만 출력하십시오.
- true → 변경되었다고 판단
- false → 변경되지 않았다고 판단
- 출력은 반드시 소문자 문자열 ("true" 또는 "false")만 포함해야 합니다.
- 설명을 절대 붙이지 마십시오.
"""


# ============================================================
# HITL 피드백 정제 함수
# ============================================================
def clean_hitl_feedback(user_feedback: str, target_node: str) -> str:
    """
    HITL 피드백 문장을 정제하여 validator에 직접 넣을 수 있는 형태로 가공

    노드 종류에 따라 피드백 정제 방식이 다름.
    - detect_changes → true/false만 반환
    - 그 외 → 자연어 한 문장
    """
    # 변경 감지 전용 처리
    if target_node == "detect_changes":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": HITL_CLEAN_PROMPT_detect_changes},
                {"role": "user", "content": user_feedback},
            ],
            temperature=0
        )
        cleaned = resp.choices[0].message.content.strip().lower()

        # 안전장치: 혹시라도 엉뚱한 값 오면 false로 강제
        if cleaned not in {"true", "false"}:
            cleaned = "false"

        return cleaned

    # -----------------------------
    # 일반 노드(map/strategy/impact) 처리
    # -----------------------------
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": HITL_CLEAN_PROMPT_GENERAL},
            {"role": "user", "content": user_feedback},
        ],
        temperature=0
    )

    cleaned = resp.choices[0].message.content.strip()
    return cleaned


# ============================================================
# validator에서 사용할 HITL state 생성
# ============================================================
def build_hitl_state(target_node: str, cleaned_feedback: str) -> dict:
    """
    HITL용 state 구성
    """

    return {
        "hitl_target_node": target_node,
        "hitl_feedback_text": cleaned_feedback,  
    }
