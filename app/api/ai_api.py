"""
module: ai_api.py
description: AI 파이프라인 실행 API
author: 조영우
created: 2025-12-04
간단 구현
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional
from scripts import run_full_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Pipeline"])


@router.post("/pipeline/run")
async def test_pipeline(citation_code: str ="21 CFR Part 1160"):
    try:
        logger.info(f"AI 파이프라인 시작: citation_code={citation_code}")
        await run_full_pipeline.run_full_pipeline(citation_code)
        return {"message": "run successful"}
    except Exception as e:
        logger.error(f"파이프라인 실행 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파이프라인 실행 실패: {str(e)}")
