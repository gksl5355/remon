# app/chatbot/intent.py
"""
REMON 챗봇의 인텐트 분류 모듈 (1) HITL 분기 필요 여부 판단 2) 어떤 노드(map / strategy / impact)인지 식별)

이 파일은 사용자 메시지가 다음 중 무엇인지 판별한다:
1) HITL (Human-In-The-Loop): 사용자가 REMON 파이프라인 결과를 수정/정정하려는 경우
2) GENERAL: 일반적인 질문 (규제 설명, 일반 대화 등)

결과는 service.py에서 다음 행동을 결정하는 데 사용된다.
"""

import os
import json
from openai import OpenAI

# -----------------------------
# OpenAI 모델 설정 (.env에서 불러옴)
# -----------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI()


# -----------------------------
# LLM에게 전달되는 인텐트 분류 프롬프트
# -----------------------------
INTENT_PROMPT = """
당신은 REMON 규제 AI 시스템의 '인텐트 분류기'입니다.

사용자 메시지를 정확히 하나의 인텐트로 분류하십시오:

------------------------------------------------------------
[인텐트 종류]

1) hitl  
- 사용자가 REMON 파이프라인 결과(매핑, 대응전략, 영향도 평가)에 대해
  '틀렸다 / 부족하다 / 다시 해라 / 고쳐라'는 식으로 수정·재실행을 요구하는 경우

예시:
  - "이 전략 이상함. 다시 만들어."
  - "mapping 틀렸어"
  - "impact 계산 다시해"
  - "여기 잘못됐음 → 고쳐"
  - "이거 이 기준으로 다시 해줘"
  - "대응전략이 너무 추상적이야. 다시 짜줘."
  - "영향도 점수 근거 부족한데 다시 평가해"
  - "이 매핑 이상한데 map 다시 해봐"

2) general  
- REMON 파이프라인 수정과 무관한 모든 일반 질문/대화
예시:
  - "이 규제 설명해줘"
  - "요약해줘"
  - "날씨 어때?"
  - "전쟁 어디에서 났어?"
  - "점심 뭐 먹을까?"
------------------------------------------------------------

[HITL일 때 target_node 판정 규칙]

intent가 "hitl"인 경우, 아래 규칙에 따라 target_node 를 선택하십시오.

1) map_products (매핑 노드)
- 사용자가 "매핑", "mapping", "맵핑" 등의 단어를 사용하며
  매핑이 틀렸거나 다시 해야 한다고 말하는 경우
예시:
  - "이 매핑 틀림. 다시 매핑해."
  - "mapping 다시"
  - "제품이랑 규제 매핑이 잘못된 것 같은데 다시 해줘"

2) generate_strategy (대응 전략 노드)
- 사용자가 "전략", "strategy", "대응", "대응전략" 등의 단어를 사용하며
  전략이 부족하다 / 다시 짜야 한다 / 이상하다고 말하는 경우
예시:
  - "대응 다시 해봐"
  - "대응전략이 너무 단순함. 다시 생성해."
  - "전략 개수 부족한데 더 만들어"
  - "전략 다시 짜줘"
  - "대응 방향 이상한데 generate_strategy 다시"

3) score_impact (영향도 평가 노드)
- 사용자가 "영향도", "impact", "점수", "스코어", "위험도" 등의 단어를 사용하며
  점수/평가를 다시 하라고 요구하는 경우
예시:
  - "영향도 계산 다시"
  - "impact 점수 이상해. 다시 평가해."
  - "점수 근거 부족한데 다시 해봐"
  - "위험도 평가 다시 돌려줘"

------------------------------------------------------------
[출력 형식]

반드시 아래 JSON 형태로만 응답하십시오:

{
  "intent": "hitl" | "general",
  "target_node": "map_products" | "generate_strategy" | "score_impact" | null
}

규칙:
- intent가 "hitl"이면, 반드시 어떤 노드에 대한 피드백인지 target_node를 채우십시오.
- intent가 "general"이면 target_node는 null로 설정하십시오.
- 사용자 메시지가 애매해도, 위 규칙을 최대한 활용하여 하나의 intent만 선택하십시오.
"""


# ============================================================
# 인텐트 분류 함수 (LLM 1회 호출)
# ============================================================
def detect_intent(user_message: str) -> dict:
    """
    사용자 메시지를 LLM에 보내 intent(hitl/general)와 target_node를 분류한다.

    Parameters
    ----------
    user_message : str
        사용자가 입력한 원본 메시지

    Returns
    -------
    dict
        {
            "intent": "hitl" | "general",
            "target_node": "map_products" | "generate_strategy" | "score_impact" | None
        }
    """
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0  # 분류는 항상 deterministic하게 수행
    )

    raw = resp.choices[0].message.content.strip()

    # LLM이 JSON을 반환하므로 파싱
    try:
        return json.loads(raw)
    except Exception:
        # LLM 반환 형식이 불안정한 경우 → 안전하게 general로 처리
        return {"intent": "general", "target_node": None}
