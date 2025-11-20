#!/usr/bin/env python
"""
Manual end-to-end runner for the LangGraph pipeline.

Usage example:
    uv run python scripts/run_full_pipeline.py \
        --pdf data/1_sample_data.pdf \
        --product-json tests/data/sample_products.json

Options:
    --use-db           Fetch product via ProductRepository (requires DB)
    --product-id ID    Target product_id when using DB or JSON fixtures
    --real-llm         Use real LLMs instead of the lightweight stubs
    --top-k N          Override mapping retrieval top_k
    --alpha F          Override mapping retrieval alpha
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
import app.ai_pipeline.nodes.generate_strategy as strategy_module

logger = logging.getLogger("run_full_pipeline")
logging.basicConfig(level=logging.INFO)


class MappingLLMStub:
    """AsyncOpenAI compatible stub used for the mapping node."""

    class _Completions:
        async def create(self, model: str, messages: List[Dict[str, Any]]):
            prompt = messages[0]["content"]
            feature_name = "unknown_feature"
            if '"name"' in prompt:
                try:
                    feature_name = (
                        prompt.split('"name"')[1].split('"')[2].strip()
                    )
                except Exception:  # pragma: no cover - defensive parsing
                    pass

            payload = {
                "applies": True,
                "required_value": "limit",
                "current_value": "current",
                "gap": "delta",
                "parsed": {
                    "category": "demo",
                    "requirement_type": "max",
                    "condition": f"{feature_name} <= limit",
                },
            }
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(payload))
                    )
                ]
            )

    class _Chat:
        def __init__(self):
            self.completions = MappingLLMStub._Completions()

    def __init__(self):
        self.chat = MappingLLMStub._Chat()


class StrategyLLMStub:
    """Minimal llm.invoke compatible stub for generate_strategy."""

    def invoke(self, prompt: str) -> str:
        return (
            "1. Update packaging warnings as described.\n"
            "2. Align formulation with the permitted threshold.\n"
            "3. Notify distributors about the regulatory change."
        )


def _load_product_from_json(path: Path, product_id: str | None) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    products: List[Dict[str, Any]] = data.get("products", [])
    if not products:
        raise ValueError(f"No products found in {path}")

    if product_id:
        for prod in products:
            if prod.get("product_id") == product_id:
                return prod
        raise ValueError(f"Product {product_id} not found in {path}")

    return products[0]


def _build_state(
    pdf_path: Path,
    use_db: bool,
    product_json: Path | None,
    product_id: str | None,
) -> AppState:
    state: AppState = {
        "preprocess_request": {
            "pdf_paths": [str(pdf_path)],
        }
    }

    if use_db:
        if not product_id:
            raise ValueError("--product-id is required with --use-db")
        state["mapping_filters"] = {"product_id": product_id}
    else:
        if not product_json:
            raise ValueError("--product-json is required when not using DB")
        product = _load_product_from_json(product_json, product_id)
        state["product_info"] = product
        state["mapping_filters"] = {"product_id": product["product_id"]}

    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangGraph pipeline end-to-end."
    )
    parser.add_argument("--pdf", required=True, type=Path, help="PDF path")
    parser.add_argument(
        "--product-json",
        type=Path,
        help="Product fixture JSON (required unless --use-db)",
    )
    parser.add_argument("--product-id", help="Target product_id")
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Fetch product info via ProductRepository",
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Use real LLM clients instead of stubs",
    )
    parser.add_argument("--top-k", type=int, help="Override mapping top_k")
    parser.add_argument("--alpha", type=float, help="Override mapping alpha")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.getLogger().setLevel(args.log_level)

    pdf_path: Path = args.pdf
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    state = _build_state(
        pdf_path=pdf_path,
        use_db=args.use_db,
        product_json=args.product_json,
        product_id=args.product_id,
    )

    mapping_context: Dict[str, Any] = {}
    if not args.real_llm:
        mapping_context["llm_client"] = MappingLLMStub()
        logger.info("Using stub LLM for mapping_node")
    if args.top_k:
        mapping_context["top_k"] = args.top_k
    if args.alpha is not None:
        mapping_context["alpha"] = args.alpha
    if mapping_context:
        state["mapping_context"] = mapping_context

    if not args.real_llm:
        # Replace the synchronous strategy LLM with a stub for deterministic output.
        strategy_module.llm = StrategyLLMStub()
        logger.info("Using stub LLM for generate_strategy")

    graph = build_graph()

    logger.info("Starting pipeline run...")
    result = await graph.ainvoke(state)
    logger.info("Pipeline finished.")

    summary = result.get("preprocess_summary", {})
    logger.info("Preprocess summary: %s", summary)

    mapping = result.get("mapping", {})
    logger.info(
        "Mapping items: %d",
        len(mapping.get("items") or []),
    )

    strategies = result.get("strategies") or result.get("strategy")
    logger.info("Strategies: %s", strategies)

    report = result.get("report")
    if report:
        logger.info("Report summary:\n%s", report.get("summary_text", report))
        if report.get("llm_report"):
            logger.info("Report (LLM):\n%s", report["llm_report"])
    else:
        logger.info("Report: %s", report)


if __name__ == "__main__":
    asyncio.run(main())
