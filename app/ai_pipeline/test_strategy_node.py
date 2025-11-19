# app/ai_pipeline/test_strategy_node.py

import asyncio
import json

from app.ai_pipeline.nodes.generate_strategy import StrategyNode

# ---------------------------------------------------------
# 🌟 Dummy MappingNode Output (StrategyNode 입력 상태)
# ---------------------------------------------------------
dummy_mapping_state = {
    "mapping": {
        "product_id": "test_001",
        "items": [
            {
                "feature_name": "nicotine_strength",
                "applies": True,
                "required_value": "10mg",
                "current_value": "12mg",
                "gap": "reduce by 2mg",
                "regulation_chunk_id": "chunk001",
                "regulation_summary": "Nicotine content must not exceed 10mg per mL.",
                "parsed": {
                    "category": "nicotine",
                    "requirement_type": "limit",
                    "condition": "must not exceed 10mg",
                },
                "metadata": {},
            }
        ],
    }
}


# ---------------------------------------------------------
# 🌟 StrategyNode 테스트 (실제 Qdrant 검색 수행)
# ---------------------------------------------------------
async def main():
    print("🚀 StrategyNode 단일 테스트 실행!")

    # StrategyNode 초기화
    node = StrategyNode() 

    # 테스트 실행
    state = await node.run(dummy_mapping_state.copy())

    result = state.get("strategy")
    items = result["items"]

    print("\n====== 📌 StrategyItem 변환 결과 ======\n")
    print("Product ID:", result["product_id"])
    print("전략 후보 개수:", len(items))

    for idx, item in enumerate(items, start=1):
        print(f"\n--- [{idx}] StrategyItem ---")
        print("Case ID:", item["case_id"])
        print("Score:", item["score"])
        print("Regulation Text:", item["regulation_text"])
        print("Strategy Text:", item["strategy_text"])
        print("Products:", item["products"])

    # ------------------------------------------------------------
    # 🔍 검색 원본 결과 출력 (Qdrant search raw result)
    # ------------------------------------------------------------
    print("\n====== 🔍 Qdrant Raw Search Results (원본 검색 데이터) ======\n")

    # StrategyNode 내부에서 검색 결과를 state에 넣지 않았기 때문에
    # 테스트에서는 다시 직접 검색해야 함
    queries = node._build_query_from_mapping(dummy_mapping_state["mapping"])
    raw_results = node._search_internal_strategies(queries)

    for idx, r in enumerate(raw_results, 1):
        print(f"\n--- Raw Result [{idx}] ---")
        print("Qdrant ID:", r["id"])
        print("Score:", r["score"])
        print("Payload Keys:", list(r["payload"].keys()))
        print("Text snippet:", r["payload"].get("text", "")[:150], "...")
        print("Full Payload:", json.dumps(r["payload"], indent=2, ensure_ascii=False))

    print("\n🎉 StrategyNode 단일 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
