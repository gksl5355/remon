#======================================================================
#langGraph 주요 흐름
#    preprocess → map_products → score_impact → generate_strategy 
#    → validate_strategy → report
# NOTE: 단일 파이프라인 구조이며, 유효성 검증 단계에서만 분기(conditional edge) 처리

#규제 변동 감지 노드 추가 고려 
#======================================================================

from langgraph.graph import StateGraph, END
from app.state.pipeline_state import AppState

# TODO: 각 노드 모듈 임포트
# 실제 프로젝트 구조에 맞게 경로 조정 필요
from app.nodes.preprocess import preprocess_node            # def preprocess_node(state: AppState) -> dict
from app.nodes.mapping import map_products_node             # def map_products_node(state: AppState) -> dict
from app.nodes.scoring import score_impact_node             # def score_impact_node(state: AppState) -> dict
from app.nodes.strategy import (
    generate_strategy_node,                                 # def generate_strategy_node(state: AppState) -> dict
    validate_strategy_node,                                 # def validate_strategy_node(state: AppState) -> dict
)
from app.nodes.report import report_node                    # def report_node(state: AppState) -> dict


#유효성(validation) 분기 처리 라우팅 처리
def _route_validation(state: AppState) -> str:
    """유효성 결과에 따라 분기: ok → report / fail → generate_strategy"""
    return "ok" if state.get("validation_strategy", True) else "fail"


def build_graph():
    graph = StateGraph(AppState)

    # 노드 등록
    graph.add_node("preprocess",          preprocess_node)
    graph.add_node("map_products",        map_products_node)
    graph.add_node("score_impact",        score_impact_node)
    graph.add_node("generate_strategy",   generate_strategy_node)
    graph.add_node("validate_strategy",   validate_strategy_node)
    graph.add_node("report",              report_node)

    # 엔트리 포인트
    graph.set_entry_point("preprocess")

    # 직선 플로우
    graph.add_edge("preprocess",        "map_products")
    graph.add_edge("map_products",      "score_impact")
    graph.add_edge("score_impact",      "generate_strategy")
    graph.add_edge("generate_strategy", "validate_strategy")

    # 유효성 분기: ok → report / fail → generate_strategy(상위로 회귀)
    graph.add_conditional_edges(
        "validate_strategy",
        _route_validation,
        {"ok": "report", "fail": "generate_strategy"},
    )

    # 종료
    graph.add_edge("report", END)

    return graph.compile()

