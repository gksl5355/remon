import asyncio
import json

from app.ai_pipeline.nodes.map_products import map_products_node
from app.ai_pipeline.nodes.report import report_node
from app.ai_pipeline.state import AppState


async def main():
    state: AppState = {
        "product_info": {
            "product_id": "4",  # 기존 DB 제품 ID가 있으면 업데이트됨
            "product_name": "demo",
            "mapping": {"target": {}, "present_state": {"nicotine": 10}},
            "feature_units": {"nicotine": "mg"},
            "country": "US",
            "category": "C",
            "regulation_trace": {},
        },
        "regulation": {
            "country": "US",
            "citation_code": "21 CFR 1141",
            "effective_date": "2024-06-01",
            "title": "Required Warnings for Cigarette Packages and Advertising",
            "regulation_id": "FDA-US-Required-Warnings-Cigarette",
        },
        "change_detection_results": [
            {
                "new_snippet": "니코틴 함량은 18mg을 초과할 수 없다...",
                "legacy_snippet": "니코틴 함량은 20mg을 초과할 수 없다...",
                "change_type": "value_change",
                "confidence_score": 0.9,
                "keywords": ["니코틴", "18mg"],
                "numerical_changes": [
                    {"legacy_value": "20mg", "new_value": "18mg"}
                ],
            }
        ],
    }

    # map_products 실행
    mapped = await map_products_node(state)
    item = mapped["mapping"]["items"][0] if mapped.get("mapping", {}).get("items") else {}
    print("=== RERANK ===")
    print(json.dumps(item.get("regulation_meta", {}).get("rerank", {}), ensure_ascii=False, indent=2))
    print("=== TRACE (in memory) ===")
    print(json.dumps(mapped.get("product_info", {}).get("regulation_trace", {}), ensure_ascii=False, indent=2))

    # report 실행 (regulation_trace가 DB에 저장됨)
    reported = await report_node(mapped)
    print("=== REPORT ===")
    print(json.dumps(reported.get("report", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
