"""
module: run_full_pipeline.py
description: REMON AI Pipeline 전체 실행 스크립트 (S3 PDF → 최종 리포트)
author: AI Agent
created: 2025-01-19
updated: 2025-01-20

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
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
from app.core.database import AsyncSessionLocal

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


def extract_metadata(vision_result: Dict[str, Any], regulation_id: int) -> Dict[str, Any]:
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
    
    logger.info(f"  ✅ Legacy 전처리 완료: {len(legacy_result['vision_extraction_result'])}페이지")
    
    # Step 3: DB 저장
    logger.info("\n[Step 3] PostgreSQL DB 저장")
    from app.core.repositories.regulation_repository import RegulationRepository
    
    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        try:
            legacy_reg = await repo.create_from_vision_result(session, legacy_result)
            await session.commit()
            logger.info(f"  ✅ Legacy 저장 완료: regulation_id={legacy_reg.regulation_id}")
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


async def run_full_pipeline():
    """전체 파이프라인 실행 (LangGraph 방식)"""

    # 테스트용 하드코딩 설정
    new_s3_key = "skala2/skala-2.4.17/regulation/US/Regulation Data B (1).pdf"
    local_new_path = "/tmp/Regulation_Data_B.pdf"
    legacy_citation_code = "FDA-21CFR-1114"  # Legacy 규제 식별용
    product_id = 1  # 테스트용 제품 ID

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

    # Step 2: Legacy regulation_id DB 조회
    logger.info("\n[Step 2] Legacy regulation_id DB 조회")
    from app.core.repositories.regulation_repository import RegulationRepository
    
    legacy_regulation_id = None
    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        try:
            # citation_code로 Legacy 검색
            legacy_reg = await repo.find_by_citation_code(
                session, 
                citation_code=legacy_citation_code
            )
            if legacy_reg:
                legacy_regulation_id = legacy_reg.regulation_id
                logger.info(f"  ✅ Legacy 발견: regulation_id={legacy_regulation_id}")
            else:
                logger.info(f"  ℹ️ Legacy 없음 (신규 규제로 처리)")
        except Exception as e:
            logger.warning(f"  ⚠️ Legacy 조회 실패: {e}")

    # Step 3: LangGraph 파이프라인 실행 (preprocess부터)
    logger.info("\n[Step 3] LangGraph 파이프라인 실행 (preprocess부터)")
    
    app = build_graph()
    
    initial_state: AppState = {
        "preprocess_request": {
            "pdf_paths": [local_new_path],
            "use_vision_pipeline": True,
            "enable_change_detection": True,
        },
        "change_context": {
            "legacy_regulation_id": legacy_regulation_id,
        },
        "mapping_filters": {"product_id": product_id},
        "validation_retry_count": 0,
    }

    try:
        final_state = await app.ainvoke(initial_state, config={"configurable": {}})
        logger.info("✅ 파이프라인 실행 완료")
    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 실패: {e}", exc_info=True)
        return

    # Step 4: 결과 출력
    logger.info("\n[Step 4] 실행 결과 요약")
    print_pipeline_summary(final_state)

    return final_state


async def main():
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(
        description="REMON AI Pipeline 실행 스크립트"
    )
    parser.add_argument(
        "--mode",
        choices=["legacy", "new"],
        default="new",
        help="실행 모드: legacy (Legacy 전처리만), new (전체 파이프라인)"
    )
    args = parser.parse_args()
    
    if args.mode == "legacy":
        await run_legacy_preprocessing()
    else:
        await run_full_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
