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
- 특히 변경 감지 HITL에서:
    - 사용자 텍스트로부터 변경 O/X(true/false) 표시
    - 이 값이 AppState.manual_change_flag에 담겨
      change_detection.py로 넘어갈 준비가 되었는지 확인
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
# 3) 챗봇 서비스 / 인텐트 / HITL 유틸 import
#    (실제 경로 구조에 맞게 조정되어 있어야 함)
# ---------------------------------------------------------
from app.ai_pipeline.nodes.chatbot.service import process_chat_message
from app.ai_pipeline.nodes.chatbot.intent import detect_intent
from app.ai_pipeline.nodes.chatbot.hitl import clean_hitl_feedback


def main():
    # LangGraph 전체 state 대신, 여기서는 간단히 dict로만 시작
    # (실제 사용 시에는 1차 그래프 실행 후의 AppState를 로드해 넣으면 됨)
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

        # -------------------------------------------------
        # 0) 인텐트 / 타깃 노드 먼저 한번 보여주기
        #    (service.py 안에서도 detect_intent를 쓰지만,
        #     여기서는 디버깅용으로 한 번 더 호출해서 눈으로 확인)
        # -------------------------------------------------
        intent_result = detect_intent(user_message)
        intent_type = intent_result.get("intent")
        target_node = intent_result.get("target_node")

        print(f"\n[Intents] intent = {intent_type}, target_node = {target_node}")

        # -------------------------------------------------
        # 1) 변경 감지 HITL인 경우: true/false → O/X 표시
        # -------------------------------------------------
        is_change_hitl = intent_type == "hitl" and target_node in {
            "detect_changes",      # graph 기준 이름
            "change_detection",    # 혹시 남아있을 수 있는 이전 이름 대비
        }

        if is_change_hitl:
            # graph 기준으로는 detect_changes가 정식 이름이지만,
            # clean_hitl_feedback은 target_node 문자열만 보고 분기하므로
            # "change_detection" / "detect_changes" 둘 다 안전하게 처리 가능
            normalized_target = "change_detection"

            cleaned_bool_str = clean_hitl_feedback(
                user_feedback=user_message,
                target_node=normalized_target,
            )  # "true" / "false"

            change_flag = cleaned_bool_str.strip().lower() == "true"
            change_mark = "O" if change_flag else "X"

            print(f"[Change HITL] LLM이 해석한 변경 여부: {cleaned_bool_str} (변경 {change_mark})")

        # -------------------------------------------------
        # 2) 실제 챗봇 서비스 호출 (validator 포함)
        # -------------------------------------------------
        result = process_chat_message(user_message, state)

        mode = result.get("mode")
        reply = result.get("reply")
        new_state = result.get("state", state)

        print(f"\n[Mode] {mode}")
        print(f"[Reply]\n{reply}\n")

        # state 업데이트 (특히 hitl일 때 validator 결과가 반영된 state)
        state = new_state

        # -------------------------------------------------
        # 3) HITL 디버그: validator 결과 + 변경감지용 manual_change_flag 확인
        # -------------------------------------------------
        if mode == "hitl":
            restarted_node = state.get("restarted_node")
            validation_result = state.get("validation_result")

            print("[HITL Debug] restarted_node =", restarted_node)
            print("[HITL Debug] validation_result =")
            print(json.dumps(validation_result, ensure_ascii=False, indent=2))
            print()

            # ✅ 변경 감지 HITL(detect_changes)인 경우 추가 디버그 출력
            if restarted_node in {"detect_changes", "change_detection"}:
                print("=== [Change Detection HITL Debug] ===")
                print("manual_change_flag  :", state.get("manual_change_flag"))
                print("needs_embedding     :", state.get("needs_embedding"))
                print("change_detection_results :", state.get("change_detection_results"))
                print("change_summary      :", state.get("change_summary"))
                print("※ 위 manual_change_flag 값이 AppState에 담겨 "
                      "change_detection_node(run) 호출 시 그대로 전달됩니다.")
                print("====================================\n")

    print("=== CLI 종료 ===")


if __name__ == "__main__":
    main()
