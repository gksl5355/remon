"""LangGraph 파이프라인 구성

흐름:
    preprocess → detect_changes → [embedding] → map_products 
    → generate_strategy → score_impact → validator → report

분기 처리:
    - detect_changes: 변경 감지 시 embedding 실행, 아니면 스킵
    - validator: 실패 시 최대 1회 재시도 (map_products/generate_strategy/score_impact)
"""

from langgraph.graph import StateGraph, END
from app.ai_pipeline.state import AppState

from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.nodes.map_products import map_products_node
from app.ai_pipeline.nodes.change_detection import change_detection_node
from app.ai_pipeline.nodes.embedding import embedding_node
from app.ai_pipeline.nodes.generate_strategy import generate_strategy_node
from app.ai_pipeline.nodes.validator import validator_node
from app.ai_pipeline.nodes.score_impact import score_impact_node
from app.ai_pipeline.nodes.report import report_node

# --------------------------------------------------------------
# Validator → 다음 노드 결정
# --------------------------------------------------------------
def _route_validation(state: AppState) -> str:
    """
    Validator 결과에 따라 다음 노드 결정.
    
    재시도 정책: 최대 2번 실행 (초기 1번 + 재시도 1번)
    2번 실패 시 강제 통과하여 HITL로 전달
    """
    decision = state.get("validation_result", {})
    restart = decision.get("restart_node")
    is_valid = decision.get("is_valid", True)
    retry_count = state.get("validation_retry_count", 0)

    # 최대 2번 실행 (초기 1번 + 재시도 1번)
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
def build_graph(start_node: str = "preprocess"):
    graph = StateGraph(AppState)

    graph.add_node("preprocess",        preprocess_node)
    graph.add_node("detect_changes",    change_detection_node)
    graph.add_node("embedding",         embedding_node)  # 임베딩 노드 추가
    graph.add_node("map_products",      map_products_node)
    graph.add_node("generate_strategy", generate_strategy_node)
    graph.add_node("score_impact",      score_impact_node)
    graph.add_node("validator",         validator_node)
    graph.add_node("report_node",       report_node)

    # entry point can be overridden for reuse (e.g., start at map_products when
    # preprocess/change_detection 결과를 재사용)
    if start_node not in {
        "preprocess",
        "detect_changes",
        "embedding",
        "map_products",
        "generate_strategy",
        "score_impact",
        "validator",
        "report_node",
    }:
        raise ValueError(f"Invalid start_node: {start_node}")
    graph.set_entry_point(start_node)

    # main flow
    graph.add_edge("preprocess", "detect_changes")
    graph.add_edge("map_products",      "generate_strategy")
    graph.add_edge("generate_strategy", "score_impact")
    graph.add_edge("score_impact",      "validator")

    # detect_changes → embedding (변경 감지 또는 신규) | map_products (변경 없음)
    graph.add_conditional_edges(
        "detect_changes",
        lambda state: "embedding" if state.get("needs_embedding", False) else "skip_embedding",
        {
            "embedding": "embedding",
            "skip_embedding": "map_products",
        }
    )
    
    # embedding → map_products
    graph.add_edge("embedding", "map_products")

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

