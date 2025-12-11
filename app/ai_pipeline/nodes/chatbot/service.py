# app/chatbot/service.py
import os
from typing import Dict, Any
import logging
from openai import OpenAI

from app.ai_pipeline.nodes.chatbot.intent import detect_intent
from app.ai_pipeline.nodes.chatbot.hitl import clean_hitl_feedback, build_hitl_state
from app.ai_pipeline.nodes.validator import validator_node

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI()


def llm_general_response(user_message: str) -> str:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "당신은 친절하고 간단 명료한 챗봇입니다."},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def process_chat_message(user_message: str, state: Dict[str, Any]) -> Dict[str, Any]:
    intent_result = detect_intent(user_message)
    intent_type = intent_result.get("intent")
    target_node = intent_result.get("target_node")

    logger.info(f"[Chatbot] intent = {intent_result}")

    # 1) 일반 대화
    if intent_type == "general":
        reply = llm_general_response(user_message)
        return {
            "mode": "general",
            "reply": reply,
            "state": state,
        }

    # 2) HITL
    if intent_type == "hitl":
        if target_node not in {
            "detect_changes",
            "map_products",
            "generate_strategy",
            "score_impact",
        }:
            return {
                "mode": "error",
                "reply": f"HITL 타깃 노드를 식별할 수 없습니다: {target_node}",
                "state": state,
            }

        # target_node에 따라:
        # - detect_changes → "true"/"false"
        # - 나머지 → 한 문장 자연어 피드백
        cleaned = clean_hitl_feedback(
            user_feedback=user_message,
            target_node=target_node,
        )

        hitl_patch = build_hitl_state(target_node, cleaned)
        state.update(hitl_patch)

        validator_output = validator_node(state)

        return {
            "mode": "hitl",
            "reply": f"HITL 적용 완료 → {target_node} 노드를 다시 실행합니다.",
            "state": validator_output,
        }

    # 3) 예외 → general fallback
    reply = llm_general_response(user_message)
    return {
        "mode": "general",
        "reply": reply,
        "state": state,
    }
