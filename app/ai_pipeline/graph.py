# app/ai_pipeline/graph.py
"""
module: graph.py
description: LangGraph 파이프라인 구성 (HITL 통합 + 번역 노드 활성화)
author: AI Agent
created: 2025-01-18
updated: 2025-01-21 (번역 노드 활성화)

흐름:
    preprocess → detect_changes → [embedding] → map_products
    → generate_strategy → score_impact → report → translate
    → (조건부) hitl → validator → ...

HITL 구조:
    - translate 이후, external_hitl_feedback 이 있을 때만 hitl 노드를 호출
    - hitl_node에서 사용자 피드백을 분석하여 state를 수정
    - validator 재실행하여 어떤 노드가 다시 실행될지 결정
"""

from langgraph.graph import StateGraph, END
from app.ai_pipeline.state import AppState

# 기존 노드들
from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.nodes.change_detection import change_detection_node
from app.ai_pipeline.nodes.embedding import embedding_node
from app.ai_pipeline.nodes.map_products import map_products_node
from app.ai_pipeline.nodes.generate_strategy import generate_strategy_node
from app.ai_pipeline.nodes.score_impact import score_impact_node
from app.ai_pipeline.nodes.validator import validator_node
from app.ai_pipeline.nodes.report import report_node
from app.ai_pipeline.nodes.translate_report import translate_report_node

# 신규 HITL 통합 노드
from app.ai_pipeline.nodes.hitl import hitl_node


# --------------------------------------------------------------
# Validator → 다음 노드 결정
# --------------------------------------------------------------
def _route_validation(state: AppState) -> str:
    """
    Validator 결과에 따라 다음 노드 결정.

    - restart_node가 있으면 해당 노드를 재실행
    - 재시도 2번 초과 시 강제 OK 처리하여 보고서 생성
    """
    decision = state.get("validation_result", {}) or {}
    restart = decision.get("restart_node")
    is_valid = decision.get("is_valid", True)
    retry_count = state.get("validation_retry_count", 0) or 0

    # 2번 넘게 실패하면 그냥 OK 처리 → report로 이동
    if retry_count >= 2:
        return "ok"

    # 정상 통과 또는 재시작 노드 없음
    if is_valid or not restart:
        return "ok"

    # change_detection 은 실제 그래프 노드 ID인 detect_changes 로 매핑
    if restart == "change_detection":
        return "detect_changes"

    # 나머지 노드 이름은 그래프 노드 ID와 동일
    if restart in ["map_products", "generate_strategy", "score_impact"]:
        return restart

    return "ok"


# --------------------------------------------------------------
# Report → 다음 노드 결정 (HITL / 종료)
# --------------------------------------------------------------
def _route_after_report(state: AppState) -> str:
    """
    report 이후 분기.

    - external_hitl_feedback 이 있으면 → hitl (다중 HITL 지원)
    - 그 외에는 → END (그래프 종료)
    """
    feedback = state.get("external_hitl_feedback")

    # 외부 HITL 피드백이 있으면 → hitl (다중 HITL 지원)
    if feedback:
        return "hitl"

    # 피드백 없으면 → 종료
    return "end"


# --------------------------------------------------------------
# Build Graph
# --------------------------------------------------------------
def build_graph(start_node: str = "preprocess"):
    graph = StateGraph(AppState)

    # -------------------------
    # 노드 등록
    # -------------------------
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("detect_changes", change_detection_node)
    graph.add_node("embedding", embedding_node)
    graph.add_node("map_products", map_products_node)
    graph.add_node("generate_strategy", generate_strategy_node)
    graph.add_node("score_impact", score_impact_node)
    graph.add_node("validator", validator_node)
    graph.add_node("report", report_node)
    graph.add_node("translate", translate_report_node)  # 번역 노드 활성화
    graph.add_node("hitl", hitl_node)

    # -------------------------
    # Entry point 설정
    # -------------------------
    if start_node not in {
        "preprocess",
        "detect_changes",
        "embedding",
        "map_products",
        "generate_strategy",
        "score_impact",
        "validator",
        "report",
        "hitl",
    }:
        raise ValueError(f"Invalid start_node: {start_node}")
    graph.set_entry_point(start_node)

    # -------------------------
    # 메인 파이프라인
    # -------------------------
    graph.add_edge("preprocess", "detect_changes")
    graph.add_edge("map_products", "generate_strategy")
    graph.add_edge("generate_strategy", "score_impact")
    # [TEST] validator 비활성화
    # graph.add_edge("score_impact", "validator")
    graph.add_edge("score_impact", "report")  # validator 우회
    graph.add_edge("report", "translate")  # 번역 노드 활성화

    # detect_changes → embedding or map_products
    graph.add_conditional_edges(
        "detect_changes",
        lambda state: "embedding" if state.get("needs_embedding", False) else "skip",
        {
            "embedding": "embedding",
            "skip": "map_products",
        },
    )

    graph.add_edge("embedding", "map_products")

    # -------------------------
    # 검증 결과에 따른 분기 [TEST: 주석처리]
    # -------------------------
    # graph.add_conditional_edges(
    #     "validator",
    #     _route_validation,
    #     {
    #         "ok": "report",
    #         "map_products": "map_products",
    #         "generate_strategy": "generate_strategy",
    #         "score_impact": "score_impact",
    #         "detect_changes": "detect_changes",
    #     },
    # )

    # -------------------------
    # 번역 후 HITL / 종료 분기
    # -------------------------
    graph.add_conditional_edges(
        "translate",
        _route_after_report,
        {
            "hitl": "hitl",
            "end": END,
        },
    )

    # HITL → 조건부 분기 (target node 재실행 또는 report)
    graph.add_conditional_edges(
        "hitl",
        lambda state: state.get("restarted_node", "report"),
        {
            "report": "report",
            "score_impact": "score_impact",
            "generate_strategy": "generate_strategy", 
            "map_products": "map_products",
            "change_detection": "detect_changes",
        },
    )

    return graph.compile()
