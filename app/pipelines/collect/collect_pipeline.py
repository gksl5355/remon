"""
module: collect_pipeline.py
description: Collect 단계 파이프라인 예시.
"""
from app.config.logger import logger

async def execute_collect(data: dict) -> dict:
    """Collect 단계 실행 함수."""
    logger.info("Collect Pipeline 실행")
    return {"stage": "collect", "result": "ok"}
