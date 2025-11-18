"""LangGraph node: translate_report"""

from __future__ import annotations

import logging

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def translate_report_node(state: AppState) -> AppState:
    """
    보고서 번역 placeholder.

    아직 번역 파이프라인이 준비되지 않아 no-op 처리한다.
    """

    logger.info("translate_report_node 실행 (placeholder)")
    # TODO(remon-ai): 다국어 번역 로직 구현
    return state


__all__ = ["translate_report_node"]

