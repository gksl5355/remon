#======================================================================
#langGraph 주요 흐름
#    preprocess → map_products → generate_strategy 
#    → validate_strategy → score_impact → report
# NOTE: 단일 파이프라인 구조이며, 유효성 검증 단계에서만 분기(conditional edge) 처리

#규제 변동 감지 노드 추가 고려 
#======================================================================

from langgraph.graph import StateGraph, END
from app.ai_pipeline.state import AppState

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


# 새로 구현한 report 노드 임포트
from app.ai_pipeline.nodes.report import report_node



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

