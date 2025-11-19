"""LangGraph node: score_impact"""

from __future__ import annotations

import logging

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def score_impact_node(state: AppState) -> AppState:
    """
    영향도 스코어링 placeholder.

    전략 결과를 받아 영향도/우선순위 산출 예정이지만 현재는 패스-스루 처리한다.
    """

    logger.info("score_impact_node 실행 (placeholder)")
    state.setdefault("impact_scores", [])
    # TODO(remon-ai): 영향도 계산 로직 구현
    return state


__all__ = ["score_impact_node"]
