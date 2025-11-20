"""LangGraph node: compose_report"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)

# 전략 LLM 재사용 (실패 시 None으로 두고 fallback 사용)
try:  # pragma: no cover - import guard
    from app.ai_pipeline.nodes.llm import llm as strategy_llm
except Exception:  # pragma: no cover
    strategy_llm = None  # type: ignore[assignment]


def _build_facts(
    preprocess_summary: Dict[str, Any],
    mapping_results: Dict[str, Any],
    strategies: List[str],
    impact_scores: List[Dict[str, Any]],
) -> str:
    """LLM에 넣을 요약용 사실 문자열을 구성한다."""
    mapping_items = mapping_results.get("items") or []
    mapping_preview = []
    for item in mapping_items[:3]:
        mapping_preview.append(
            f"{item.get('feature_name')}: required={item.get('required_value')} "
            f"current={item.get('current_value')} applies={item.get('applies')}"
        )

    impact_preview = []
    for score in impact_scores[:2]:
        impact_preview.append(
            f"{score.get('impact_level')}/score={score.get('weighted_score')} "
            f"reason={score.get('reasoning', '')[:60]}"
        )

    lines = [
        f"Preprocess status={preprocess_summary.get('status', 'unknown')} "
        f"(processed={preprocess_summary.get('processed_count', 0)}, "
        f"succeeded={preprocess_summary.get('succeeded', 0)}, "
        f"failed={preprocess_summary.get('failed', 0)})",
        f"Mapping items={len(mapping_items)} preview={'; '.join(mapping_preview) or '없음'}",
        f"Strategies count={len(strategies)} preview={'; '.join(strategies[:3]) or '없음'}",
        f"Impact entries={len(impact_scores)} preview={'; '.join(impact_preview) or '없음'}",
    ]
    return "\n".join(lines)


def _call_llm_for_report(facts: str) -> Optional[str]:
    """LLM을 호출해 한국어 보고서 문구를 생성한다."""
    if not strategy_llm:
        return None

    prompt = f"""
다음 파이프라인 실행 결과를 바탕으로 한국어 요약 보고서를 작성해 주세요.
- 각 노드별 성공/실패 여부와 핵심 결과를 한 문단으로 정리해 주세요.
- 너무 길게 쓰지 말고, 실행 상태를 한눈에 볼 수 있도록 간결하게 작성하세요.
- 숫자나 개수는 사실 그대로만 사용하세요. 새로운 수치는 만들지 마세요.

[실행 결과]
{facts}
"""
    try:
        return strategy_llm.invoke(prompt)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LLM 보고서 생성 실패: %s", exc)
        return None


async def report_node(state: AppState) -> AppState:
    """
    파이프라인 실행 결과를 요약하는 간단한 리포트 노드.
    - preprocess / mapping / strategy / impact / report 생성 여부를 요약한다.
    - 나중에 정식 리포트 템플릿이 준비될 때까지 임시 테스트 용도로 사용한다.
    """

    preprocess_summary = state.get("preprocess_summary") or {}
    mapping_results = state.get("mapping") or state.get("mapping_results") or {}
    strategies = state.get("strategies") or []
    impact_scores = state.get("impact_scores") or []

    # 간단한 단계별 상태 판단
    preprocess_status = preprocess_summary.get("status") or "unknown"
    mapping_count = len(mapping_results.get("items") or [])
    strategy_count = len(strategies)
    impact_count = len(impact_scores)

    sections = [
        {
            "title": "Preprocess",
            "status": preprocess_status,
            "detail": f"processed={preprocess_summary.get('processed_count', 0)} "
                      f"succeeded={preprocess_summary.get('succeeded', 0)} "
                      f"failed={preprocess_summary.get('failed', 0)}",
        },
        {
            "title": "Mapping",
            "status": "ok" if mapping_count > 0 else "empty",
            "detail": f"items={mapping_count}",
        },
        {
            "title": "Strategy",
            "status": "ok" if strategy_count > 0 else "empty",
            "detail": f"strategies={strategy_count}",
        },
        {
            "title": "ImpactScore",
            "status": "ok" if impact_count > 0 else "empty",
            "detail": f"entries={impact_count}",
        },
    ]

    # 간단한 텍스트 요약을 함께 저장
    summary_lines = [
        f"Preprocess: {preprocess_status} "
        f"(processed={preprocess_summary.get('processed_count', 0)}, "
        f"succeeded={preprocess_summary.get('succeeded', 0)}, "
        f"failed={preprocess_summary.get('failed', 0)})",
        f"Mapping: {'ok' if mapping_count else 'empty'} (items={mapping_count})",
        f"Strategy: {'ok' if strategy_count else 'empty'} (strategies={strategy_count})",
        f"ImpactScore: {'ok' if impact_count else 'empty'} (entries={impact_count})",
    ]
    summary_text = "\n".join(summary_lines)

    # LLM 보고서 생성 (실패 시 None)
    facts = _build_facts(
        preprocess_summary,
        mapping_results,
        strategies,
        impact_scores,
    )
    llm_report = _call_llm_for_report(facts)

    logger.info("report_node summary:\n%s", summary_text)
    if llm_report:
        logger.info("report_node LLM 보고서:\n%s", llm_report)

    state["report"] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "draft",
        "sections": sections,
        "summary_text": summary_text,
        "llm_report": llm_report,
        "facts": facts,
    }
    return state


__all__ = ["report_node"]
