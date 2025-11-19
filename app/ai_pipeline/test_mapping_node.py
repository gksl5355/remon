# app/ai_pipeline/test_mapping.py

import asyncio
from openai import AsyncOpenAI

from app.ai_pipeline.nodes.map_products import MappingNode
from app.ai_pipeline.state import AppState

async def main():
    # 1) LLM 클라이언트 준비
    llm = AsyncOpenAI()

    # 2) 단일 노드 인스턴스 생성
    node = MappingNode(
        llm_client=llm,
        top_k=5,   # 원하는 대로
    )

    # 3) 테스트용 state 준비
    #    - mapping_filters.product_id를 넣어주면 DB에서 product fetch 됨
    state: AppState = {
        "mapping_filters": {
            "product_id": 1
        }
    }

    # 4) 노드 실행
    result_state = await node.run(state)

    print("\n===== 🚀 MappingNode 결과 =====\n")
    mapping = result_state.get("mapping")
    print(f"총 매핑 개수: {len(mapping['items'])}")
    for item in mapping["items"][:5]:  # 일부만 출력
        print("\n--- mapping item ---")
        print("feature:", item["feature_name"])
        print("applies:", item["applies"])
        print("summary:", item["regulation_summary"])

if __name__ == "__main__":
    asyncio.run(main())
