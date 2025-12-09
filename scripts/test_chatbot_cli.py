# scripts/test_chatbot_cli.py
"""
REMON 챗봇 + HITL + Validator 연동 간단 CLI 테스트 스크립트

사용법:
    uv run python scripts/test_chatbot_cli.py
또는
    python scripts/test_chatbot_cli.py

기능:
- 사용자 입력을 받아 process_chat_message(...) 호출
- intent(general / hitl) 분류가 제대로 되는지 확인
- hitl일 때 validator_node가 잘 호출되는지 확인
"""

import os
import sys
import json

from dotenv import load_dotenv

# ---------------------------------------------------------
# 1) .env 로드 (OPENAI_API_KEY, OPENAI_MODEL 등)
# ---------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------
# 2) 프로젝트 루트(remon/)를 sys.path에 추가
#    scripts/ 기준으로 한 단계 위가 remon/
# ---------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# ---------------------------------------------------------
# 3) 챗봇 서비스 레이어 import
# ---------------------------------------------------------
from app.ai_pipeline.nodes.chatbot.service import process_chat_message


def main():
    # LangGraph 전체 state 대신, 여기서는 간단히 dict로만 시작
    state = {}

    print("=== REMON Chatbot + HITL + Validator 테스트 CLI ===")
    print("종료하려면 'exit' 또는 'quit' 입력\n")

    while True:
        try:
            user_message = input("User> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if user_message.lower() in {"exit", "quit"}:
            print("종료합니다.")
            break

        # 챗봇 서비스 호출
        result = process_chat_message(user_message, state)

        mode = result.get("mode")
        reply = result.get("reply")
        new_state = result.get("state", state)

        print(f"\n[Mode] {mode}")
        print(f"[Reply]\n{reply}\n")

        # state 업데이트 (특히 hitl일 때 validator 결과가 반영된 state)
        state = new_state

        # ---- 디버그용: hitl일 때 validator 결과 조금 더 보여주기 ----
        if mode == "hitl":
            restarted_node = state.get("restarted_node")
            validation_result = state.get("validation_result")

            print("[HITL Debug] restarted_node =", restarted_node)
            print("[HITL Debug] validation_result =")
            print(json.dumps(validation_result, ensure_ascii=False, indent=2))
            print()

    print("=== CLI 종료 ===")


if __name__ == "__main__":
    main()
