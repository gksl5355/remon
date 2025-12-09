"""
module: run_full_pipeline.py
description: REMON AI Pipeline 전체 실행 스크립트 (S3 PDF → 최종 리포트)
author: AI Agent
created: 2025-01-19
updated: 2025-01-20 15:30 (LangSmith 트레이싱 추가)

실행 방법:
    # Legacy 규제 전처리 (1회만)
    python scripts/run_full_pipeline.py --mode legacy

    # New 규제 처리 (전체 파이프라인)
    python scripts/run_full_pipeline.py --mode new
    python scripts/run_full_pipeline.py  # 기본값 = new
"""

import asyncio
import logging
import sys
import argparse
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import text

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.state import AppState
from app.core.database import AsyncSessionLocal
<<<<<<< HEAD
from langsmith import traceable
=======
from app.core.repositories.product_repository import ProductRepository
>>>>>>> 1e0417fe55574192e20f4d78f81a95f57b1dc6ad

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
            f'logs/pipeline_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
    ],
)
logger = logging.getLogger(__name__)


def extract_metadata(
    vision_result: Dict[str, Any], regulation_id: int
) -> Dict[str, Any]:
    """Vision 결과에서 regulation 메타데이터 추출"""
    pages = vision_result.get("vision_extraction_result", [])
    if not pages:
        return {
            "country": "US",
            "title": "Unknown Regulation",
            "effective_date": None,
            "regulation_id": regulation_id,
        }

    first_page = pages[0]
    metadata = first_page.get("structure", {}).get("metadata", {})

    return {
        "country": metadata.get("jurisdiction_code", "US"),
        "title": metadata.get("title", "Unknown Regulation"),
        "effective_date": metadata.get("effective_date"),
        "citation_code": metadata.get("citation_code"),
        "authority": metadata.get("authority"),
        "regulation_id": regulation_id,
    }


def print_pipeline_summary(final_state: AppState):
    """파이프라인 실행 결과 요약 출력"""
    logger.info("\n" + "=" * 80)
    logger.info("📋 파이프라인 실행 결과 요약")
    logger.info("=" * 80)

    # 변경 감지
    change_summary = final_state.get("change_summary", {})
    if change_summary:
        logger.info(f"\n🔍 변경 감지:")
        logger.info(f"  - 상태: {change_summary.get('status')}")
        logger.info(f"  - 변경 건수: {change_summary.get('total_changes', 0)}")
        logger.info(f"  - 고신뢰도: {change_summary.get('high_confidence_changes', 0)}")

        # 변경 상세
        change_results = final_state.get("change_detection_results", [])
        if change_results:
            logger.info(f"\n  📝 변경 상세 (상위 5개):")
            for idx, result in enumerate(change_results[:5], 1):
                if result.get("change_detected"):
                    logger.info(
                        f"    {idx}. [{result.get('section_ref')}] "
                        f"{result.get('change_type')} - {result.get('confidence_level')}"
                    )

    # 매핑
    mapping = final_state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    if mapping_items:
        logger.info(f"\n🔗 제품-규제 매핑:")
        logger.info(f"  - 매핑 항목: {len(mapping_items)}개")
        applies_count = sum(1 for item in mapping_items if item.get("applies"))
        logger.info(f"  - 적용 대상: {applies_count}개")

    # 전략
    strategies = final_state.get("strategies", [])
    if strategies:
        logger.info(f"\n💡 대응 전략:")
        logger.info(f"  - 전략 개수: {len(strategies)}개")
        for i, strategy in enumerate(strategies[:3], 1):
            logger.info(f"  {i}. {strategy[:80]}...")

    # 영향도
    impact_scores = final_state.get("impact_scores", [])
    if impact_scores:
        impact = impact_scores[0]
        logger.info(f"\n📊 영향도 평가:")
        logger.info(f"  - 영향도: {impact.get('impact_level')}")
        logger.info(f"  - 점수: {impact.get('weighted_score'):.2f}")

    # 리포트
    report = final_state.get("report", {})
    if report:
        logger.info(f"\n📋 최종 리포트:")
        logger.info(f"  - 생성 시각: {report.get('generated_at')}")
        logger.info(f"  - 섹션 수: {len(report.get('sections', []))}")
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

    # 테스트용 하드코딩 설정
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

    if legacy_result["status"] != "success":
        logger.error("❌ Legacy 전처리 실패")
        return

    logger.info(
        f"  ✅ Legacy 전처리 완료: {len(legacy_result['vision_extraction_result'])}페이지"
    )

    # Step 3: DB 저장
    logger.info("\n[Step 3] PostgreSQL DB 저장")
    from app.core.repositories.regulation_repository import RegulationRepository

    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        try:
            legacy_reg = await repo.create_from_vision_result(session, legacy_result)
            await session.commit()
            logger.info(
                f"  ✅ Legacy 저장 완료: regulation_id={legacy_reg.regulation_id}"
            )
            logger.info(f"  ✅ citation_code: {legacy_reg.citation_code}")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ DB 저장 실패: {e}")
            import traceback

            traceback.print_exc()
            return

    logger.info("\n" + "=" * 80)
    logger.info("🎉 Legacy 규제 전처리 완료!")
    logger.info("=" * 80)


<<<<<<< HEAD
@traceable(name="REMON_Full_Pipeline", run_type="chain")
async def run_full_pipeline():
=======
async def run_full_pipeline(citation_code: str):
>>>>>>> 1e0417fe55574192e20f4d78f81a95f57b1dc6ad
    """전체 파이프라인 실행 (LangGraph 방식)"""

    # 테스트용 하드코딩 설정
    new_s3_key = "skala2/skala-2.4.17/regulation/US/Regulation Data B (1).pdf"
    local_new_path = "/tmp/Regulation_Data_B.pdf"
    legacy_citation_code = citation_code  # Legacy 규제 식별용 동일 citation 사용

    logger.info("=" * 80)
    logger.info("🚀 REMON AI Pipeline 전체 실행 시작")
    logger.info("=" * 80)

    # Step 1: S3에서 New 규제 PDF 다운로드
    try:
        logger.info("\n[Step 1] S3에서 New 규제 PDF 다운로드")
        await download_pdf_from_s3(new_s3_key, local_new_path)
        logger.info(f"   ✅ New: {local_new_path}")
    except Exception as e:
        logger.error(f"❌ 파일 다운로드 실패: {e}")
        return

    # Step 2: LangGraph 파이프라인 실행 (DB 전체 제품 자동 처리)
    logger.info("\n[Step 2] LangGraph 파이프라인 실행 (DB 전체 제품 자동 처리)")
    logger.info("  ℹ️ Legacy 검색은 change_detection_node에서 자동 수행됩니다")
    logger.info("  ℹ️ 제품 매핑은 map_products_node에서 DB 전체 제품을 자동 조회합니다")

    app = build_graph()

    initial_state: AppState = {
        "preprocess_request": {
            "pdf_paths": [local_new_path],
            "use_vision_pipeline": True,
            "enable_change_detection": True,
        },
        "change_context": {},  # Legacy는 change_detection_node가 자동 검색
        "mapping_filters": {},  # 빈 딕셔너리: map_products_node가 DB에서 자동 조회
        "validation_retry_count": 0,
    }
    # Step 2: Legacy regulation_id DB 조회
    logger.info("\n[Step 2] Legacy regulation_id DB 조회")
    from app.core.repositories.regulation_repository import RegulationRepository
    
    legacy_regulation_id = None
    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        # Step 2: Legacy regulation_id DB 조회
        try:
            legacy_reg = await repo.find_by_citation_code(
                session,
                citation_code=legacy_citation_code,
            )
            if legacy_reg:
                legacy_regulation_id = legacy_reg.regulation_id
                logger.info(f"  ✅ Legacy 발견: regulation_id={legacy_regulation_id}")
            else:
                logger.info("  ℹ️ Legacy 없음 (신규 규제로 처리)")
        except Exception as e:
            logger.warning(f"  ⚠️ Legacy 조회 실패: {e}")

        # Step 3: 최신/이전 규제 ID 결정 (DB 기준)
        logger.info("\n[Step 3] 규제 ID 결정 (citation_code 기반)")
        new_regulation_id = None
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

        # Step 4: 전처리(+변경 감지) 1회 실행 → 결과 재사용하여 제품별 매핑
        logger.info("\n[Step 4] 전처리/변경 감지 1회 실행 → 결과 재사용하여 제품별 매핑")

        # 4-1. 전처리 1회 (enable_change_detection=True 이면 내부에서 변경 감지까지 수행)
        base_state: AppState = {
            "preprocess_request": {
                "pdf_paths": [local_new_path],
                "use_vision_pipeline": True,
                "enable_change_detection": True,
            },
            "change_context": {
                "legacy_regulation_id": legacy_regulation_id,
                "new_regulation_id": new_regulation_id,
            },
            "validation_retry_count": 0,
        }
        base_state = await preprocess_node(base_state)

        # 제품 목록 조회 (별도 세션 사용)
        product_ids = []
        try:
            async with AsyncSessionLocal() as product_session:
                result = await product_session.execute(
                    text("SELECT product_id FROM products ORDER BY product_id")
                )
                product_ids = [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error(f"제품 목록 조회 실패: {e}")
            return

        if not product_ids:
            logger.error("제품이 없습니다. products 테이블을 확인하세요.")
            return

        # 제품별 매핑/전략/리포트만 실행하는 그래프
        app = build_graph(start_node="map_products")

        final_state = None
        for pid in product_ids:
            logger.info(f"▶️ 제품 {pid}에 대해 파이프라인 실행 (전처리 재사용)")
            per_product_state: AppState = copy.deepcopy(base_state)
            per_product_state.update(
                {
                    "mapping_filters": {"product_id": pid},
                    "validation_retry_count": 0,
                }
            )

            try:
                final_state = await app.ainvoke(per_product_state, config={"configurable": {}})
                logger.info(f"✅ 제품 {pid} 파이프라인 실행 완료")
            except Exception as e:
                logger.error(f"❌ 제품 {pid} 파이프라인 실행 실패: {e}", exc_info=True)
                continue

    if final_state:
        logger.info("\n[Step 5] 실행 결과 요약 (마지막 제품 기준)")
        print_pipeline_summary(final_state)

    return final_state


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
        default="21 CFR Part 1160",
        help="규제 식별용 citation_code (legacy/new 매칭에 사용)"
    )
    args = parser.parse_args()

    if args.mode == "legacy":
        await run_legacy_preprocessing()
    else:
        await run_full_pipeline(citation_code=args.citation_code)


if __name__ == "__main__":
    asyncio.run(main())
