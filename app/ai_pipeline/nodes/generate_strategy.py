"""
Placeholder node for strategy generation.
"""

from __future__ import annotations

import logging

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def generate_strategy_node(state: AppState) -> AppState:
    logger.info("generate_strategy_node 실행 (placeholder)")
    # TODO(remon-ai): 실제 전략 생성 로직 구현 예정
    return state


__all__ = ["generate_strategy_node"]
