#!/usr/bin/env python3
"""
HITL 통합 노드 단독 테스트 스크립트

목적:
  - app.ai_pipeline.nodes.hitl.hitl_node 가
    1) 인텐트 분류 (hitl / general)
    2) target_node 결정
    3) 피드백 정제
    4) state 패치 (manual_change_flag, needs_embedding, refined_*_prompt 등)
    5) validator_node 호출 → validation_result / restarted_node 설정

  이 흐름대로 잘 동작하는지 CLI에서 바로 확인하기 위함.

사용 예:
  uv run python scripts/test_hitl_node.py
"""

import sys
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.state import AppState
from app.ai_pipeline.nodes.hitl import hitl_node, detect_hitl_intent




def make_dummy_state() -> AppState:
    """
    HITL 동작 확인용 최소 더미 state 생성.

    - mapping / strategies / impact_scores / regulation: validator가 먹을 기본값
    - change_detection_*: 변경 감지 HITL 테스트용 더미 값
    """
    return {
        # validator 입력용 더미 값들
        "mapping": {
            "product_id": "P-TEST",
            "product_name": "Test Product",
            "items": [],
        },
        "strategies": [
            "초기 전략 예시 1",
            "초기 전략 예시 2",
        ],
        "impact_scores": [
            {
                "raw_scores": {"severity": 3, "likelihood": 2},
                "reasoning": "초기 더미 영향도",
                "weighted_score": 5.0,
                "impact_level": "medium",
            }
        ],
        "regulation": {
            "title": "Dummy Regulation for HITL Test",
            "regulation_id": "DUMMY-REG",
        },

        # 변경 감지 결과 더미 (HITL로 어떻게 초기화되는지 보기 위함)
        "change_detection_results": [
            {"section_ref": "1160.5(a)", "change_detected": True, "confidence_level": "LOW"}
        ],
        "change_summary": {
            "status": "completed",
            "total_changes": 1,
            "high_confidence_changes": 0,
        },
        "change_detection_index": {
            "1160.5": {"change_detected": True}
        },

        # validator retry 카운터
        "validation_retry_count": 0,
    }


def print_state_diff(state: AppState):
    """
    HITL 적용 후 핵심 필드만 요약해서 출력.
    (전체 state 덤프는 너무 길어서, 눈으로 확인 필요한 것만 뽑음)
    """
    print("\n=== [HITL Debug] 핵심 State 요약 ===")

    # 변경 감지 관련
    print(f"manual_change_flag     : {state.get('manual_change_flag')}")
    print(f"needs_embedding        : {state.get('needs_embedding')}")
    print(f"change_summary         : {state.get('change_summary')}")
    print(f"change_detection_index : {bool(state.get('change_detection_index'))}")

    # 매핑 / 전략 / 영향도 초기화 여부
    mapping = state.get("mapping")
    strategies = state.get("strategies")
    impact_scores = state.get("impact_scores")

    print(f"mapping is None        : {mapping is None}")
    print(f"strategies is None     : {strategies is None}")
    print(f"impact_scores is None  : {impact_scores is None}")

    # validator 결과
    validation_result = state.get("validation_result") or {}
    print(f"validation_result      : {json.dumps(validation_result, ensure_ascii=False)}")
    print(f"restarted_node         : {state.get('restarted_node')}")

    # refined prompt 여부
    for key in [
        "refined_map_products_prompt",
        "refined_generate_strategy_prompt",
        "refined_score_impact_prompt",
    ]:
        if key in state:
            print(f"{key} 존재 여부     : True (길이={len(str(state[key]))} chars)")
        else:
            print(f"{key} 존재 여부     : False")

    print("====================================\n")


def main():
    print("=" * 80)
    print("🤖 REMON HITL Node 단독 테스트 CLI")
    print("=" * 80)
    print(" - 이 스크립트는 LangGraph 전체가 아니라 hitl_node + validator_node 흐름만 검증합니다.")
    print(" - state는 더미 데이터로 시작하고, 매번 HITL 입력에 따라 갱신됩니다.")
    print(" - 종료: 'exit' / 'quit' / '완료' / 빈 입력(엔터)")
    print("=" * 80)

    state: AppState = make_dummy_state()

    while True:
        try:
            user_msg = input("\nUser> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n입력이 중단되었습니다. 종료합니다.")
            break

        if not user_msg or user_msg.lower() in {"exit", "quit", "완료"}:
            print("\nHITL 테스트를 종료합니다.")
            break

        # 1) 인텐트 분류 (디버그용)
        intent = detect_hitl_intent(user_msg)
        print(
            f"\n[Intents] intent = {intent.get('intent')}, "
            f"target_node = {intent.get('target_node')}"
        )

        # 2) hitl_node 가 읽을 external_hitl_feedback 세팅
        state["external_hitl_feedback"] = user_msg

        # 3) validator retry 카운터 초기화 (HITL 사이클이므로 별도)
        state["validation_retry_count"] = 0

        # 4) HITL 노드 호출 → 내부에서 validator_node 까지 실행
        state = hitl_node(state)

        # 5) 결과 요약 출력
        print_state_diff(state)


if __name__ == "__main__":
    main()
