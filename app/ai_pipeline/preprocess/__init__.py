"""
Preprocessing entrypoints exposed to the LangGraph pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.ai_pipeline.state import AppState, PreprocessRequest, PreprocessSummary

if TYPE_CHECKING:  # pragma: no cover
    from app.ai_pipeline.preprocess.preprocess_orchestrator import (
        PreprocessOrchestrator,
    )

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
    """Blocking 전처리 작업을 별도 스레드에서 실행 (기존 방식)."""
    orchestrator = _get_orchestrator()
    return await asyncio.to_thread(orchestrator.process_pdf, pdf_path)


async def _run_vision_orchestrator(
    pdf_path: str, vision_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Vision Pipeline 실행.

    Args:
        pdf_path: PDF 파일 경로
        vision_config: Vision 설정 딕셔너리 (None이면 기본값 사용)
            - api_key: OpenAI API 키 (필수)
            - max_concurrency: 최대 동시 실행 수 (기본값: 3)
            - token_budget: 토큰 예산 (기본값: None)
            - request_timeout: 요청 타임아웃 초 (기본값: 120)
            - retry_max_attempts: 최대 재시도 횟수 (기본값: 2)
            - retry_backoff_seconds: 재시도 대기 시간 초 (기본값: 1.0)
            - 기타 설정들...
    """
    from app.ai_pipeline.preprocess.vision_orchestrator import VisionOrchestrator
    from app.ai_pipeline.preprocess.config import PreprocessConfig

    # LangSmith 초기화
    PreprocessConfig.setup_langsmith()

    # vision_config가 제공되면 인자로 전달, 없으면 기본값 사용
    if vision_config:
        orchestrator = VisionOrchestrator(**vision_config)
    else:
        orchestrator = VisionOrchestrator()
    return await asyncio.to_thread(orchestrator.process_pdf, pdf_path)


def _resolve_pdf_paths(state: AppState) -> List[str]:
    """
    PDF 경로 결정 우선순위:
    1. state["preprocess_request"]["pdf_paths"] (직접 지정)
    2. state["preprocess_request"]["load_from_s3"] = True (S3 자동 로드)
    3. 빈 리스트 (스킵)
    """
    request: PreprocessRequest | None = state.get("preprocess_request")

    if not request:
        return []

    # 1. 직접 지정된 경로
    pdf_paths = request.get("pdf_paths", [])
    if pdf_paths:
        return pdf_paths

    # 2. S3 자동 로드
    if request.get("load_from_s3"):
        from app.ai_pipeline.preprocess.s3_loader import load_today_regulations

        target_date = request.get("s3_date")  # YYYYMMDD or None
        logger.info("📥 S3에서 오늘 날짜 규제 파일 자동 로드")

        s3_paths = load_today_regulations(target_date)
        return s3_paths

    return []


async def preprocess_node(state: AppState) -> AppState:
    """
    LangGraph preprocess node.

    기대 입력:
        state["preprocess_request"] = {
            "pdf_paths": ["/path/a.pdf", ...],
            "product_info": {...},  # 선택 사항
            "use_vision_pipeline": bool,  # True면 Vision Pipeline 사용
            "vision_config": {  # 선택 사항, Vision Pipeline 설정
                "api_key": "sk-...",  # 필수
                "max_concurrency": 3,
                "token_budget": 100000,
                "request_timeout": 120,
                "retry_max_attempts": 2,
                "retry_backoff_seconds": 1.0,
                # 기타 설정들...
            }
        }
    출력:
        state["preprocess_results"]  # 각 PDF 처리 결과 리스트
        state["preprocess_summary"]  # 진행 상태 메타데이터
        state["vision_extraction_result"]  # Vision Pipeline 사용 시
        state["graph_data"]  # Vision Pipeline 사용 시
        state["dual_index_summary"]  # Vision Pipeline 사용 시
    """

    # PDF 경로 결정 (직접 지정 또는 S3 자동 로드)
    pdf_paths: List[str] = _resolve_pdf_paths(state)

    request: PreprocessRequest | None = state.get("preprocess_request") or {}
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

    # Vision Pipeline 사용 여부 확인
    use_vision = request.get("use_vision_pipeline", False)

    logger.info(
        "preprocess_node 시작: %d개 PDF (Vision: %s)", len(pdf_paths), use_vision
    )

    processed_results: List[Dict[str, Any]] = []
    success_count = 0
    all_vision_results = []
    all_graph_data = {"nodes": [], "edges": []}
    all_index_summaries = []

    # Vision Pipeline 설정 (preprocess_request에서 가져오기)
    vision_config = request.get("vision_config") if use_vision else None

    for pdf_path in pdf_paths:
        try:
            if use_vision:
                result = await _run_vision_orchestrator(
                    pdf_path, vision_config=vision_config
                )
            else:
                result = await _run_orchestrator(pdf_path)

            result.setdefault("pdf_path", pdf_path)

            # 🔥 DB에 저장하고 regulation_id 추가
            if result.get("status") == "success" and use_vision:
                from app.core.repositories.regulation_repository import (
                    RegulationRepository,
                )
                from app.core.database import AsyncSessionLocal

                async with AsyncSessionLocal() as session:
                    repo = RegulationRepository()
                    try:
                        regulation = await repo.create_from_vision_result(
                            session, result
                        )
                        await session.commit()
                        result["regulation_id"] = regulation.regulation_id
                        logger.info(
                            f"✅ DB 저장 완료: regulation_id={regulation.regulation_id}"
                        )
                        
                        # 🔑 change_context 자동 채우기 (변경 감지용)
                        if request.get("enable_change_detection"):
                            state["change_context"] = {
                                "new_regulation_id": regulation.regulation_id,
                                "new_regul_data": result,
                            }
                            logger.info("✅ change_context 자동 설정 완료")
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"❌ DB 저장 실패: {e}")

            processed_results.append(result)

            if result.get("status") == "success":
                success_count += 1

                # Vision Pipeline 결과 수집
                if use_vision:
                    all_vision_results.extend(
                        result.get("vision_extraction_result", [])
                    )

                    graph_data = result.get("graph_data", {})
                    all_graph_data["nodes"].extend(graph_data.get("nodes", []))
                    all_graph_data["edges"].extend(graph_data.get("edges", []))

                    if result.get("dual_index_summary"):
                        all_index_summaries.append(result["dual_index_summary"])

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

    # Vision Pipeline 결과 저장
    if use_vision and all_vision_results:
        state["vision_extraction_result"] = all_vision_results
        state["graph_data"] = all_graph_data
        state["dual_index_summary"] = {
            "total_chunks": sum(s.get("qdrant_chunks", 0) for s in all_index_summaries),
            "total_nodes": len(all_graph_data["nodes"]),
            "total_edges": len(all_graph_data["edges"]),
            "summaries": all_index_summaries,
        }

    # product_info가 Preprocess 단계에서 전달되는 경우 상태에 반영
    if request.get("product_info"):
        state["product_info"] = request["product_info"]

    logger.info(
        "preprocess_node 완료: success=%d, failed=%d",
        success_count,
        fail_count,
    )

    # 변경 감지 활성화 시 regulation 메타데이터 추가
    if request.get("enable_change_detection") and processed_results:
        first_result = processed_results[0]
        if first_result.get("status") == "success" and use_vision:
            vision_pages = first_result.get("vision_extraction_result", [])
            if vision_pages:
                structure = vision_pages[0].get("structure", {})
                metadata = structure.get("metadata") or {}
                state["regulation"] = {
                    "country": metadata.get("jurisdiction_code", "US"),
                    "title": metadata.get("title", "Unknown Regulation"),
                    "effective_date": metadata.get("effective_date"),
                    "citation_code": metadata.get("citation_code"),
                    "authority": metadata.get("authority"),
                    "regulation_id": first_result.get("regulation_id"),
                }
                logger.info("✅ regulation 메타데이터 추가 완료")

    return state


__all__ = ["preprocess_node"]
