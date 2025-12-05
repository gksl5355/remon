#======================================================================
#langGraph 주요 흐름
#    preprocess → map_products → generate_strategy 
#    → validate_strategy → score_impact → report
# NOTE: 단일 파이프라인 구조이며, 유효성 검증 단계에서만 분기(conditional edge) 처리

#규제 변동 감지 노드 추가 고려 
#======================================================================
<<<<<<< HEAD
=======
#======================================================================
# langGraph 주요 흐름
#    preprocess → map_products → generate_strategy 
#    → validator → score_impact → report
#======================================================================
>>>>>>> origin/main

from langgraph.graph import StateGraph, END
from app.ai_pipeline.state import AppState

<<<<<<< HEAD
# TODO: 각 노드 모듈 임포트
# 실제 프로젝트 구조에 맞게 경로 조정 필요
from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.nodes.map_products import map_products_node      # def map_products_node(state: AppState) -> dict
from app.ai_pipeline.nodes.generate_strategy import (                 # def generate_strategy_node(state: AppState) -> dict
    generate_strategy_node,                                           # def validate_strategy_node(state: AppState) -> dict
    validate_strategy_node,
)
from app.ai_pipeline.nodes.score_impact import score_impact_node      # def score_impact_node(state: AppState) -> dict
from app.ai_pipeline.nodes.report import report_node                  # def report_node(state: AppState) -> dict


# 유효성(validation) 분기 라우팅
def _route_validation(state: AppState) -> str:
    """유효성 결과에 따라 분기: ok → score_impact / fail → generate_strategy"""
    return "ok" if getattr(state, "validation_strategy", True) else "fail"


def build_graph():
    graph = StateGraph(AppState)

    # 노드 등록
    graph.add_node("preprocess",          preprocess_node)
    graph.add_node("map_products",        map_products_node)
    graph.add_node("generate_strategy",   generate_strategy_node)
    graph.add_node("validate_strategy",   validate_strategy_node)
    graph.add_node("score_impact",        score_impact_node)
    graph.add_node("report",              report_node)

    # 엔트리 포인트
    graph.set_entry_point("preprocess")

    # 전처리 → 제품 매핑 → 대응전략 생성
    graph.add_edge("preprocess",        "map_products")
    graph.add_edge("map_products",      "generate_strategy")
    graph.add_edge("generate_strategy", "validate_strategy")

    # 유효성 분기: ok → score_impact / fail → generate_strategy(재생성)
    graph.add_conditional_edges(
        "validate_strategy",
        _route_validation,
        {"ok": "score_impact", "fail": "generate_strategy"},
    )

    # 영향도 → 리포트 → 종료
    graph.add_edge("score_impact", "report")
    graph.add_edge("report", END)

    return graph.compile()

=======
from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.nodes.map_products import map_products_node
from app.ai_pipeline.nodes.change_detection import change_detection_node
from app.ai_pipeline.nodes.generate_strategy import generate_strategy_node
from app.ai_pipeline.nodes.validator import validator_node
from app.ai_pipeline.nodes.score_impact import score_impact_node
from app.ai_pipeline.nodes.report import report_node

# --------------------------------------------------------------
# Validator → 다음 노드 결정
# --------------------------------------------------------------
def _route_validation(state: AppState) -> str:
    decision = state.get("validation_result", {})
    restart = decision.get("restart_node")
    is_valid = decision.get("is_valid", True)
    retry_count = state.get("validation_retry_count", 0)

    # ----------------------------------------
    # 🔥 Self-refine는 딱 1번만 허용
    # (validator 실행은 2번까지, 재시도는 1번만)
    # ----------------------------------------
    if retry_count >= 2:
        return "ok"

    # 정상일 때
    if is_valid:
        return "ok"

    # 오류 + retry_count < 2 이면 → 재생성 노드로 이동
    if restart in ["map_products", "generate_strategy", "score_impact"]:
        return restart

    return "ok"



# --------------------------------------------------------------
# Build Graph
# --------------------------------------------------------------
def build_graph():
    graph = StateGraph(AppState)

    graph.add_node("preprocess",        preprocess_node)
    graph.add_node("detect_changes",    change_detection_node)
    graph.add_node("map_products",      map_products_node)
    graph.add_node("generate_strategy", generate_strategy_node)
    graph.add_node("score_impact",      score_impact_node)
    graph.add_node("validator",         validator_node)    # node name OK
    graph.add_node("report_node",       report_node)       # node_name만 변경

    graph.set_entry_point("preprocess")

    # preprocess → detect_changes
    graph.add_edge("preprocess", "detect_changes")

    # detect_changes → map_products | terminate
    graph.add_conditional_edges(
        "detect_changes",
        lambda state: "terminate"
        if state.get("change_detection", {}).get("terminated")
        else "proceed",
        {
            "terminate": END,
            "proceed": "map_products",
        }
    )

    # main flow
    graph.add_edge("map_products",      "generate_strategy")
    graph.add_edge("generate_strategy", "score_impact")
    graph.add_edge("score_impact",      "validator")

    # validator → validation only for 3 nodes
    graph.add_conditional_edges(
        "validator",
        _route_validation,
        {
            "ok": "report_node",              # 마지막 노드
            "map_products": "map_products",   # 실패 시 재시도 노드들
            "generate_strategy": "generate_strategy",
            "score_impact": "score_impact",
        },
    )

    # report → END
    graph.add_edge("report_node", END)

    return graph.compile()



>>>>>>> origin/main
