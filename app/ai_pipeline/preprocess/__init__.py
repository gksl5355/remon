"""
Preprocessing entrypoints exposed to the LangGraph pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, TYPE_CHECKING

from app.ai_pipeline.state import AppState, PreprocessRequest, PreprocessSummary

if TYPE_CHECKING:  # pragma: no cover
    from app.ai_pipeline.preprocess.preprocess_orchestrator import PreprocessOrchestrator

logger = logging.getLogger(__name__)

_orchestrator: "PreprocessOrchestrator | None" = None


def _get_orchestrator() -> PreprocessOrchestrator:
    """Lazy 초기화된 PreprocessOrchestrator 반환."""
    global _orchestrator
    if _orchestrator is None:
        from app.ai_pipeline.preprocess.preprocess_orchestrator import (
            PreprocessOrchestrator,
        )
        _orchestrator = PreprocessOrchestrator()
    return _orchestrator


async def _run_orchestrator(pdf_path: str) -> Dict[str, Any]:
    """Blocking 전처리 작업을 별도 스레드에서 실행."""
    orchestrator = _get_orchestrator()
    return await asyncio.to_thread(orchestrator.process_pdf, pdf_path)


async def preprocess_node(state: AppState) -> AppState:
    """
    LangGraph preprocess node.

    기대 입력:
        state["preprocess_request"] = {
            "pdf_paths": ["/path/a.pdf", ...],
            "product_info": {...}  # 선택 사항
        }
    출력:
        state["preprocess_results"]  # 각 PDF 처리 결과 리스트
        state["preprocess_summary"]  # 진행 상태 메타데이터
    """

    request: PreprocessRequest | None = state.get("preprocess_request")

    if not request:
        logger.info("preprocess_node skipped – preprocess_request 없음")
        summary: PreprocessSummary = {
            "status": "skipped",
            "processed_count": 0,
            "succeeded": 0,
            "failed": 0,
            "reason": "preprocess_request missing",
        }
        state["preprocess_summary"] = summary
        return state

    pdf_paths: List[str] = request.get("pdf_paths", [])
    if not pdf_paths:
        logger.info("preprocess_node skipped – pdf_paths 비어있음")
        summary = {
            "status": "skipped",
            "processed_count": 0,
            "succeeded": 0,
            "failed": 0,
            "reason": "pdf_paths missing",
        }
        state["preprocess_summary"] = summary
        return state

    logger.info("preprocess_node 시작: %d개 PDF", len(pdf_paths))

    processed_results: List[Dict[str, Any]] = []
    success_count = 0

    for pdf_path in pdf_paths:
        try:
            result = await _run_orchestrator(pdf_path)
            # process_pdf 결과에는 pdf_path가 없으므로 추적용으로 추가
            result.setdefault("pdf_path", pdf_path)
            processed_results.append(result)
            if result.get("status") == "success":
                success_count += 1
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("PDF 전처리 실패: %s", pdf_path)
            processed_results.append(
                {
                    "pdf_path": pdf_path,
                    "status": "error",
                    "error": str(exc),
                }
            )

    fail_count = len(processed_results) - success_count
    summary_status: str
    if success_count == len(processed_results):
        summary_status = "completed"
    elif success_count == 0:
        summary_status = "error"
    else:
        summary_status = "partial"

    state["preprocess_results"] = processed_results
    summary: PreprocessSummary = {
        "status": summary_status,
        "processed_count": len(processed_results),
        "succeeded": success_count,
        "failed": fail_count,
        "reason": None,
    }
    state["preprocess_summary"] = summary

    # product_info가 Preprocess 단계에서 전달되는 경우 상태에 반영
    if request.get("product_info"):
        state["product_info"] = request["product_info"]

    logger.info(
        "preprocess_node 완료: success=%d, failed=%d",
        success_count,
        fail_count,
    )

    return state


__all__ = ["preprocess_node"]
