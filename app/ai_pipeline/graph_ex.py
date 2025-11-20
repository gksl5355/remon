"""
graph_ex.py
---------------------------------------
LangGraph Pipeline Demo (NO PREPROCESS)
규제 문장만 입력 → map_products → generate_strategy 
→ validator → score_impact → report 까지 실행
---------------------------------------
"""

import asyncio
from pprint import pprint

from langgraph.graph import StateGraph, END
from app.ai_pipeline.state import AppState

# 👇 실제 Node import
from app.ai_pipeline.nodes.map_products import map_products_node
from app.ai_pipeline.nodes.generate_strategy import generate_strategy_node
from app.ai_pipeline.nodes.validator import validator
from app.ai_pipeline.nodes.score_impact import score_impact_node
from app.ai_pipeline.nodes.report import report_node


# ---------------------------------------------------------
# Validation routing
# ---------------------------------------------------------
def _route_validation(state: AppState) -> str:
    return "ok" if state.get("validation_strategy", True) else "fail"


# ---------------------------------------------------------
# Build Graph (Preprocess 완전 제외)
# ---------------------------------------------------------
def build_graph():
    graph = StateGraph(AppState)

    # 노드 등록
    graph.add_node("map_products", map_products_node)
    graph.add_node("generate_strategy", generate_strategy_node)
    graph.add_node("validator", validator)
    graph.add_node("score_impact", score_impact_node)
    graph.add_node("report", report_node)

    # 엔트리 포인트 → map_products
    graph.set_entry_point("map_products")

    # 기본 흐름
    graph.add_edge("map_products", "generate_strategy")
    graph.add_edge("generate_strategy", "validator")

    # validation 분기
    graph.add_conditional_edges(
        "validator",
        _route_validation,
        {"ok": "score_impact", "fail": "generate_strategy"},
    )

    graph.add_edge("score_impact", "report")
    graph.add_edge("report", END)

    return graph.compile()


# ---------------------------------------------------------
# DEMO 실행
# ---------------------------------------------------------
async def run_demo():

    graph = build_graph()

    # 🔥 규제 문장만 넣어서 실행
    initial_state: AppState = {
        "regulation": {
            "text": "Nicotine content must be reduced below 0.5 mg"
        },

        # OPTIONAL: 특정 product_id 원하면 넣기
        # "mapping_filters": {"product_id": 1}
    }

    print("\n======================")
    print("🔍 LangGraph STREAM 시작")
    print("======================")

    # 각 노드 상태 실시간 보기
    async for event in graph.astream(initial_state):
        print("\n==================== Event ====================")

        node = event.get("node")
        if node:
            print(f"🟡 Node: {node}")
        else:
            print(f"🟡 Event: {event.get('event')}")

        pprint(event.get("state"))


    print("\n======================")
    print("🏁 FINAL STATE")
    print("======================")

    final_state = await graph.ainvoke(initial_state)
    pprint(final_state)

    print("\n----------------------")
    print("📄 최종 Report Draft")
    print("----------------------")
    pprint(final_state.get("report"))


# ---------------------------------------------------------
# Script Entry
# ---------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(run_demo())
