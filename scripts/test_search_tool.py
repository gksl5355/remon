"""
Simple standalone checker for the regulation search tool.

- Default query is set to a nicotine/tobacco keyword so you can quickly verify
  whether the hybrid retriever returns anything meaningful.
- You can override the query/top_k/alpha or pass Qdrant filters as JSON.

Example:
    python scripts/test_search_tool.py \
        --query "담배 니코틴 함량" \
        --top-k 5 \
        --alpha 0.7
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is on sys.path when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ai_pipeline.tools.retrieval_tool import get_retrieval_tool
from app.config.settings import settings


def _parse_filters(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse filter JSON from CLI; exit early on invalid JSON."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[error] Failed to parse --filters JSON: {exc}")
        sys.exit(2)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quick check for the search tool.")
    parser.add_argument(
        "--query",
        default="담배 니코틴 함량",
        help="Search text to send to the hybrid retriever.",
    )
    parser.add_argument(
        "--top-k",
        dest="top_k",
        type=int,
        default=settings.MAPPING_TOP_K,
        help="Number of candidates to request.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=settings.MAPPING_ALPHA,
        help="Dense weight for hybrid fusion (0-1).",
    )
    parser.add_argument(
        "--filters",
        help="Optional Qdrant filters as JSON string, e.g. '{\"country\": \"KR\"}'.",
    )
    parser.add_argument(
        "--show-metadata",
        action="store_true",
        help="Include payload metadata in the output.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    filters = _parse_filters(args.filters)
    search_tool = get_retrieval_tool()

    try:
        result = await search_tool.search(
            query=args.query,
            strategy="hybrid",
            top_k=args.top_k,
            alpha=args.alpha,
            filters=filters,
        )
    except Exception as exc:  # pragma: no cover - diagnostic helper
        print(f"[error] Search failed: {exc}")
        return 1

    meta = result.get("metadata", {})
    print(
        f"query='{meta.get('query', args.query)}' "
        f"top_k={meta.get('top_k', args.top_k)} "
        f"alpha={meta.get('alpha', args.alpha)} "
        f"filters={meta.get('filters') or filters or '{}'}"
    )

    hits = result.get("results", [])
    if not hits:
        print("No results returned.")
        return 0

    for idx, item in enumerate(hits, start=1):
        score = item.get("scores", {}).get("final_score")
        score_display = f"{score:.4f}" if score is not None else "n/a"
        snippet = (item.get("text") or "").replace("\n", " ")
        snippet = snippet[:200] + ("…" if len(snippet) > 200 else "")
        print(f"{idx:02d}. id={item.get('id')} score={score_display}")
        print(f"     text: {snippet}")
        if args.show_metadata:
            print(f"     meta: {json.dumps(item.get('metadata', {}), ensure_ascii=False)}")

    return 0


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
