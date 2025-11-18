"""
Placeholder node for strategy validation.
"""

from __future__ import annotations

import logging

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def validate_strategy_node(state: AppState) -> AppState:
    logger.info("validate_strategy_node 실행 (placeholder)")
    state["validation_strategy"] = True
    # TODO(remon-ai): 전략 품질 검증 및 재생성 조건 구현 예정
    return state


__all__ = ["validate_strategy_node"]
