# scripts/run_full_pipeline.py
"""
module: run_full_pipeline.py
description: REMON AI Pipeline 전체 실행 스크립트 (S3 PDF → 최종 리포트)
author: AI Agent
created: 2025-01-19
updated: 2025-01-21 (함수 시그니처 통합: traceable + citation_code 파라미터)

실행 방법:
    # Legacy 규제 전처리 (1회만)
    python scripts/run_full_pipeline.py --mode legacy

    # New 규제 처리 (전체 파이프라인 + HITL 대화)
    python scripts/run_full_pipeline.py --mode new
    python scripts/run_full_pipeline.py  # 기본값 = new
"""

import asyncio
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import text

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
from app.core.database import AsyncSessionLocal
from langsmith import traceable

# 로그 디렉토리 생성
Path("logs").mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)
logger = logging.getLogger(__name__)


def print_pipeline_summary(final_state: AppState):
    """파이프라인 실행 결과 요약 출력"""
    logger.info("\n" + "=" * 80)
    logger.info("📋 파이프라인 실행 결과 요약")
    logger.info("=" * 80)

    # 변경 감지
    change_summary = final_state.get("change_summary", {})
    if change_summary:
        logger.info("\n🔍 변경 감지:")
        logger.info(f"  - 상태: {change_summary.get('status')}")
        logger.info(f"  - 변경 건수: {change_summary.get('total_changes', 0)}")
        logger.info(f"  - 고신뢰도: {change_summary.get('high_confidence_changes', 0)}")

        # 변경 상세
        change_results = final_state.get("change_detection_results", [])
        if change_results:
            logger.info("\n  📝 변경 상세 (상위 5개):")
            for idx, result in enumerate(change_results[:5], 1):
                if result.get("change_detected"):
                    logger.info(
                        f"    {idx}. [{result.get('section_ref')}] "
                        f"{result.get('change_type')} - {result.get('confidence_level')}"
                    )

    # 매핑
    mapping = final_state.get("mapping", {}) or {}
    mapping_items = mapping.get("items", []) or []
    if mapping_items:
        logger.info("\n🔗 제품-규제 매핑:")
        logger.info(f"  - 매핑 항목: {len(mapping_items)}개")
        applies_count = sum(1 for item in mapping_items if item.get("applies"))
        logger.info(f"  - 적용 대상: {applies_count}개")

    # 전략
    strategies = final_state.get("strategies", []) or []
    if strategies:
        logger.info("\n💡 대응 전략:")
        logger.info(f"  - 전략 개수: {len(strategies)}개")
        for i, strategy in enumerate(strategies[:3], 1):
            logger.info(f"  {i}. {str(strategy)[:80]}...")

    # 영향도
    impact_scores = final_state.get("impact_scores", []) or []
    if impact_scores:
        impact = impact_scores[0] or {}
        try:
            score = float(impact.get("weighted_score", 0.0))
        except Exception:
            score = 0.0
        logger.info("\n📊 영향도 평가:")
        logger.info(f"  - 영향도: {impact.get('impact_level')}")
        logger.info(f"  - 점수: {score:.2f}")
    else:
        logger.info("\n📊 영향도 평가: 없음")

    # 리포트
    report = final_state.get("report", {}) or {}
    if report:
        logger.info("\n📋 최종 리포트:")
        logger.info(f"  - 생성 시각: {report.get('generated_at')}")
        logger.info(f"  - 섹션 수: {len(report.get('sections', []) or [])}")
        logger.info(f"  - Report ID: {report.get('report_id')}")

    logger.info("\n" + "=" * 80)
    logger.info("🎉 전체 파이프라인 실행 완료!")
    logger.info("=" * 80)


async def download_pdf_from_s3(s3_key: str, local_path: str) -> str:
    """S3에서 PDF 다운로드"""
    import boto3

    logger.info(f"📥 S3에서 PDF 다운로드 중: {s3_key}")

    s3_client = boto3.client("s3")
    bucket = "arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage"

    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    s3_client.download_file(bucket, s3_key, local_path)
    logger.info(f"✅ 다운로드 완료: {local_path}")
    return local_path


async def run_legacy_preprocessing():
    """Legacy 규제 전처리 및 DB 저장 (1회만 실행)"""

    legacy_s3_key = "skala2/skala-2.4.17/regulation/US/Regulation Data A (1).pdf"
    local_legacy_path = "/tmp/Regulation_Data_A.pdf"

    logger.info("=" * 80)
    logger.info("🔧 Legacy 규제 전처리 모드")
    logger.info("=" * 80)

    # Step 1: S3에서 Legacy PDF 다운로드
    try:
        logger.info("\n[Step 1] S3에서 Legacy 규제 PDF 다운로드")
        await download_pdf_from_s3(legacy_s3_key, local_legacy_path)
        logger.info(f"   ✅ Legacy: {local_legacy_path}")
    except Exception as e:
        logger.error(f"❌ 파일 다운로드 실패: {e}")
        return

    # Step 2: Legacy 전처리
    logger.info("\n[Step 2] Legacy 규제 전처리 (Vision Pipeline)")
    from app.ai_pipeline.preprocess.vision_orchestrator import VisionOrchestrator

    orchestrator = VisionOrchestrator()
    legacy_result = await orchestrator.process_pdf_async(
        local_legacy_path, use_parallel=True, language_code=None
    )

    if legacy_result.get("status") != "success":
        logger.error("❌ Legacy 전처리 실패")
        return

    logger.info(f"  ✅ Legacy 전처리 완료: {len(legacy_result.get('vision_extraction_result', []))}페이지")

    # Step 3: DB 저장
    logger.info("\n[Step 3] PostgreSQL DB 저장")
    from app.core.repositories.regulation_repository import RegulationRepository

    regulation_id = None
    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        try:
            legacy_reg = await repo.create_from_vision_result(session, legacy_result)
            await session.commit()
            regulation_id = legacy_reg.regulation_id
            logger.info(f"  ✅ Legacy 저장 완료: regulation_id={regulation_id}")
            logger.info(f"  ✅ citation_code: {legacy_reg.citation_code}")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ DB 저장 실패: {e}")
            import traceback

            traceback.print_exc()
            return

    # Step 4: 임베딩 (Qdrant 저장)
    logger.info("\n[Step 4] 임베딩 및 VectorDB 저장")
    from app.ai_pipeline.preprocess.semantic_processing import DualIndexer

    chunks = legacy_result.get("chunks", []) or []
    graph_data = legacy_result.get("graph_data", {"nodes": [], "edges": []}) or {"nodes": [], "edges": []}
    vision_results = legacy_result.get("vision_extraction_result", []) or []

    if chunks:
        indexer = DualIndexer()
        index_summary = indexer.index(
            chunks=chunks,
            graph_data=graph_data,
            source_file=Path(local_legacy_path).name,
            regulation_id=regulation_id,
            vision_results=vision_results,
        )
        logger.info(f"  ✅ 임베딩 완료: {index_summary.get('qdrant_chunks', 0)}개 청크")
    else:
        logger.warning("  ⚠️ 청크 없음, 임베딩 스킵")

    logger.info("\n" + "=" * 80)
    logger.info("🎉 Legacy 규제 전처리 완료 (임베딩 포함)!")
    logger.info("=" * 80)


@traceable(name="REMON_Full_Pipeline", run_type="chain")
async def run_full_pipeline(citation_code: str | None = None):
    """
    전체 파이프라인 실행 (S3 자동 로드 + LangGraph + HITL 루프)

    1차 실행:
        - preprocess → ... → validator → report → END

    HITL 재실행:
        - hitl 를 엔트리 포인트로 사용 (✅ validator보다 먼저 HITL 해석)
        - hitl → validator(HITL) → fallback 노드 → ... → report → END
    """

    logger.info("=" * 80)
    logger.info("🚀 REMON AI Pipeline 전체 실행 시작")
    logger.info("=" * 80)

    # ------- 그래프 컴파일 -------
    # 1) 전체 자동 실행용 (preprocess부터)
    app_full = build_graph(start_node="preprocess")

    # 2) HITL 재실행용 (hitl부터) ✅
    app_hitl = build_graph(start_node="hitl")

    # Step 1: Legacy regulation_id DB 조회 (citation_code 기반) - 선택
    logger.info("\n[Step 1] Legacy regulation_id DB 조회")
    from app.core.repositories.regulation_repository import RegulationRepository

    legacy_regulation_id = None
    new_regulation_id = None

    if citation_code:
        async with AsyncSessionLocal() as session:
            repo = RegulationRepository()
            try:
                legacy_reg = await repo.find_by_citation_code(
                    session,
                    citation_code=citation_code,
                )
                if legacy_reg:
                    legacy_regulation_id = legacy_reg.regulation_id
                    logger.info(f"  ✅ Legacy 발견: regulation_id={legacy_regulation_id}")
                else:
                    logger.info("  ℹ️ Legacy 없음 (신규 규제로 처리)")
            except Exception as e:
                logger.warning(f"  ⚠️ Legacy 조회 실패: {e}")

    # Step 2: 최신/이전 규제 ID 결정 (DB 기준)
    logger.info("\n[Step 2] 규제 ID 결정 (citation_code 기반)")
    if citation_code:
        async with AsyncSessionLocal() as session:
            repo = RegulationRepository()
            try:
                latest, previous = await repo.find_latest_and_previous_by_citation(
                    session, citation_code
                )
                if latest:
                    new_regulation_id = latest.regulation_id
                    logger.info(f"  ✅ 최신 규제: regulation_id={new_regulation_id}")
                if previous:
                    legacy_regulation_id = previous.regulation_id
                    logger.info(f"  ✅ 이전(legacy): regulation_id={legacy_regulation_id}")
                elif not legacy_regulation_id:
                    logger.info("  ℹ️ 이전 버전 없음")
            except Exception as e:
                logger.warning(f"  ⚠️ 규제 ID 결정 실패: {e}")
    else:
        logger.info("  ℹ️ citation_code 미지정 → 전처리/변경감지 단계에서 자동 추출")

    # Step 3: 전체 파이프라인 1회 실행 (자동 모드)
    logger.info("\n[Step 3] 전체 파이프라인 1회 실행 (자동 모드)")
    logger.info("  ℹ️ S3에서 오늘 업로드된 파일 자동 로드 (skala2/skala-2.4.17/test)")
    logger.info("  ℹ️ 전처리에서 추출한 국가 정보로 제품 자동 필터링")
    logger.info("  ℹ️ change_detection_node에서 Legacy 자동 검색 및 비교")

    state: AppState = {
        "preprocess_request": {
            "load_from_s3": True,           # S3 자동 로드 활성화
            "s3_date": None,                # None이면 오늘 날짜
            "use_vision_pipeline": True,
            "enable_change_detection": True,
        },
        "change_context": {},               # 전처리 후 자동 채워짐
        "mapping_filters": {},
        "validation_retry_count": 0,
    }

    try:
        # ✅ 1차 실행은 preprocess부터 전체 파이프라인
        state = await app_full.ainvoke(state, config={"configurable": {}})
        logger.info("✅ 1차 파이프라인 실행 완료")
    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 실패: {e}", exc_info=True)
        return

    if state:
        logger.info("\n[Step 4] 1차 실행 결과 요약")
        print_pipeline_summary(state)

    # ------------------------------------------------------------------
    # Step 5: HITL 인터랙티브 루프
    #   - 사람이 결과를 보고 피드백을 입력하면
    #     → external_hitl_feedback 에 넣고 HITL 그래프(hitl entry)로 재실행
    #   - 그래프 안에서는:
    #       hitl → validator(HITL) → restart_node → ... → report → END
    # ------------------------------------------------------------------
    logger.info("\n[Step 5] HITL 피드백 루프 시작 (엔터만 입력하면 종료)")

    while True:
        print("\n" + "-" * 80)
        print("💬 결과에 대한 HITL 피드백을 입력하세요.")
        print("   - 예) '변경 없음으로 처리해줘', '매핑 다시 해줘', '전략 좀 더 보수적으로'")
        print("   - 아무것도 입력하지 않고 엔터 → HITL 종료")
        print("   - 'exit' / 'quit' / '완료' 입력 → HITL 종료")
        print("-" * 80)

        try:
            feedback = input("HITL> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHITL 입력이 중단되었습니다. 파이프라인을 종료합니다.")
            break

        if not feedback or feedback.lower() in {"exit", "quit", "완료"}:
            logger.info("HITL 루프 종료 요청 → 파이프라인 종료.")
            break

        # 그래프에서 hitl_node가 읽을 입력값 주입
        state["external_hitl_feedback"] = feedback

        # validator 자동 retry 카운터 초기화 (HITL는 별도 사이클)
        state["validation_retry_count"] = 0

        # 안전하게 이전 HITL 메타데이터도 초기화
        state.pop("hitl_target_node", None)
        state.pop("hitl_feedback_text", None)
        state.pop("hitl_feedback", None)
        state.pop("hitl_session_active", None)

        logger.info(f"[HITL] 새로운 피드백으로 그래프 재실행 (hitl entry): '{feedback}'")
        logger.info(f"[HITL] State 전: external_hitl_feedback={state.get('external_hitl_feedback')}, hitl_target_node={state.get('hitl_target_node')}")

        try:
            # ✅ HITL 재실행은 hitl을 엔트리포인트로 사용하는 그래프
            state = await app_hitl.ainvoke(state, config={"configurable": {}})
            logger.info("✅ HITL 반영 후 파이프라인 재실행 완료")
            logger.info(f"[HITL] State 후: external_hitl_feedback={state.get('external_hitl_feedback')}, hitl_target_node={state.get('hitl_target_node')}")
        except Exception as e:
            logger.error(f"❌ HITL 재실행 중 오류: {e}", exc_info=True)
            break

        # 재실행 결과 요약
        logger.info("\n[HITL] 재실행 결과 요약")
        print_pipeline_summary(state)

    return state


async def main():
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="REMON AI Pipeline 실행 스크립트")
    parser.add_argument(
        "--mode",
        choices=["legacy", "new"],
        default="new",
        help="실행 모드: legacy (Legacy 전처리만), new (전체 파이프라인)",
    )
    parser.add_argument(
        "--citation-code",
        default=None,
        help="(선택) 규제 식별용 citation_code (미지정 시 전처리에서 자동 추출)",
    )
    args = parser.parse_args()

    if args.mode == "legacy":
        await run_legacy_preprocessing()
    else:
        await run_full_pipeline(citation_code=args.citation_code)


if __name__ == "__main__":
    asyncio.run(main())
