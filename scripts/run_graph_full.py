"""
Test driver to run the full LangGraph (preprocess → detect_changes → map_products
→ generate_strategy → score_impact → validator → report) for a single product.
Use this to verify node wiring without the batch optimizations.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
from scripts.run_full_pipeline import print_pipeline_summary  # reuse logger + summary


logger = logging.getLogger(__name__)


def _print_change_detection_state(final_state: AppState, limit: int = 10):
    """Debug helper: dump change_detection_results contents."""
    results = final_state.get("change_detection_results") or []
    summary = final_state.get("change_summary") or {}

    logger.info("\n" + "=" * 80)
    logger.info("🔍 Change Detection State Dump")
    logger.info("=" * 80)
    logger.info(
        "status=%s total=%s high=%s",
        summary.get("status"),
        summary.get("total_changes"),
        summary.get("high_confidence_changes"),
    )

    for idx, item in enumerate(results[:limit], 1):
        logger.info(
            "[%d] section=%s detected=%s type=%s conf=%.2f level=%s",
            idx,
            item.get("section_ref"),
            item.get("change_detected"),
            item.get("change_type"),
            item.get("confidence_score", 0.0),
            item.get("confidence_level"),
        )
        num_changes = item.get("numerical_changes") or []
        if num_changes:
            logger.info("    numerical_changes: %s", num_changes)
        legacy_snip = (item.get("legacy_snippet") or "")[:200]
        new_snip = (item.get("new_snippet") or "")[:200]
        if legacy_snip or new_snip:
            logger.info("    legacy: %s", legacy_snip)
            logger.info("    new   : %s", new_snip)
    if len(results) > limit:
        logger.info("... (%d more)", len(results) - limit)


def _build_state(args: argparse.Namespace) -> AppState:
    """Assemble initial state for a single full-graph run."""
    preprocess_request: Dict[str, Any] = {
        "pdf_paths": [args.pdf],
        "use_vision_pipeline": args.use_vision,
        "enable_change_detection": args.enable_change_detection,
    }

    change_context: Dict[str, Optional[Any]] = {}
    if args.new_regulation_id:
        change_context["new_regulation_id"] = args.new_regulation_id
    if args.legacy_regulation_id:
        change_context["legacy_regulation_id"] = args.legacy_regulation_id

    state: AppState = {
        "preprocess_request": preprocess_request,
        "change_context": change_context,
        "mapping_filters": {"product_id": args.product_id},
        "validation_retry_count": 0,
    }
    return state


async def _main_async(args: argparse.Namespace) -> int:
    app = build_graph(start_node="preprocess")
    state = _build_state(args)

    try:
        final_state = await app.ainvoke(state, config={"configurable": {}})
    except Exception as exc:  # pragma: no cover - diagnostic driver
        logger.error("❌ Full graph run failed: %s", exc, exc_info=True)
        return 1

    logger.info("✅ Full graph run completed")
    print_pipeline_summary(final_state)
    _print_change_detection_state(final_state)
    return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run full LangGraph once for a single product (connectivity test)."
    )
    parser.add_argument(
        "--pdf",
        default="/tmp/Regulation_Data_B.pdf",
        help="Local PDF path for preprocess node.",
    )
    parser.add_argument(
        "--product-id",
        type=int,
        default=4,
        help="Target product_id for mapping filters.",
    )
    parser.add_argument(
        "--new-regulation-id",
        type=int,
        default=None,
        help="regulation_id of the new regulation (for change_detection).",
    )
    parser.add_argument(
        "--legacy-regulation-id",
        type=int,
        default=None,
        help="regulation_id of the legacy regulation (for change_detection).",
    )
    parser.add_argument(
        "--use-vision",
        action="store_true",
        help="Enable Vision pipeline during preprocess.",
    )
    parser.add_argument(
        "--no-vision",
        dest="use_vision",
        action="store_false",
        help="Disable Vision pipeline during preprocess.",
    )
    parser.set_defaults(use_vision=True)

    parser.add_argument(
        "--enable-change-detection",
        action="store_true",
        help="Run change_detection inside preprocess.",
    )
    parser.add_argument(
        "--disable-change-detection",
        dest="enable_change_detection",
        action="store_false",
        help="Skip change_detection.",
    )
    parser.set_defaults(enable_change_detection=True)

    args = parser.parse_args()
    exit_code = asyncio.run(_main_async(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
