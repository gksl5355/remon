"""
module: run_full_pipeline.py
description: REMON AI Pipeline 전체 실행 스크립트 (S3 PDF → 최종 리포트)
author: AI Agent
created: 2025-01-19
updated: 2025-12-08

실행 방법:
    python scripts/run_full_pipeline.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

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


async def run_full_pipeline():
    """전체 파이프라인 실행 (LangGraph 방식)"""

    # 1. 파일 다운로드 (S3 경로 예시)
    legacy_s3_key = "skala2/skala-2.4.17/regulation/US/Regulation Data A (1).pdf"
    new_s3_key = "skala2/skala-2.4.17/regulation/US/Regulation Data B (1).pdf"

    local_legacy_path = "/tmp/Regulation_Data_A.pdf"
    local_new_path = "/tmp/Regulation_Data_B.pdf"

    print("=" * 80)
    print("🚀 REMON AI Pipeline 전체 실행 시작")
    print("=" * 80)

    try:
        print("\n[Step 1] S3에서 PDF 다운로드")
        await download_pdf_from_s3(legacy_s3_key, local_legacy_path)
        await download_pdf_from_s3(new_s3_key, local_new_path)
        print(f"   ✅ Legacy: {local_legacy_path}")
        print(f"   ✅ New: {local_new_path}")

    except Exception as e:
        logger.error(f"❌ 파일 다운로드 실패: {e}")
        return

    # 2. Legacy 규제 전처리 (Data A)
    logger.info("\n[Step 2] Legacy 규제 (Data A) 전처리")
    from app.ai_pipeline.preprocess.vision_orchestrator import VisionOrchestrator

    orchestrator = VisionOrchestrator()
    legacy_result = await orchestrator.process_pdf_async(
        local_legacy_path, use_parallel=True, language_code="en"
    )

    if legacy_result["status"] != "success":
        logger.error("❌ Legacy 전처리 실패")
        return

    logger.info(f"  ✅ Legacy 전처리 완료: {len(legacy_result['vision_extraction_result'])}페이지")

    # 3. New 규제 전처리 (Data B)
    logger.info("\n[Step 3] New 규제 (Data B) 전처리")
    
    new_result = await orchestrator.process_pdf_async(
        local_new_path, use_parallel=True, language_code="en"
    )

    if new_result["status"] != "success":
        logger.error("❌ New 전처리 실패")
        return

    logger.info(f"  ✅ New 전처리 완료: {len(new_result['vision_extraction_result'])}페이지")

    # 4. DB 저장 (Legacy + New)
    logger.info("\n[Step 4] PostgreSQL DB 저장")
    from app.core.repositories.regulation_repository import RegulationRepository
    
    legacy_regulation_id = None
    new_regulation_id = None
    
    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        
        try:
            legacy_reg = await repo.create_from_vision_result(session, legacy_result)
            await session.flush()
            legacy_regulation_id = legacy_reg.regulation_id
            logger.info(f"  ✅ Legacy 저장: regulation_id={legacy_regulation_id}")
            
            new_reg = await repo.create_from_vision_result(session, new_result)
            await session.flush()
            new_regulation_id = new_reg.regulation_id
            logger.info(f"  ✅ New 저장: regulation_id={new_regulation_id}")
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ DB 저장 실패: {e}")
            import traceback
            traceback.print_exc()
            return
    
    # 5. 변경 감지 (A vs B)
    logger.info("\n[Step 5] 변경 감지 (Data A vs Data B)")
    from app.ai_pipeline.nodes.change_detection import change_detection_node

    change_state: AppState = {
        "change_context": {
            "new_regulation_id": new_regulation_id,
            "legacy_regulation_id": legacy_regulation_id,
        },
        "vision_extraction_result": new_result["vision_extraction_result"],
    }
    
    change_state = await change_detection_node(change_state, config={"configurable": {}})

    change_summary = change_state.get("change_summary", {})
    logger.info(f"  ✅ 변경 감지 완료: {change_summary.get('total_changes', 0)}개 변경")

    # 6. LangGraph 파이프라인 실행
    logger.info("\n[Step 6] LangGraph 파이프라인 실행")
    
    app = build_graph()
    
    initial_state: AppState = {
        "preprocess_results": [new_result],
        "preprocess_summary": {"status": "completed", "succeeded": 1},
        "vision_extraction_result": new_result["vision_extraction_result"],
        "mapping_filters": {"product_id": None},
        "regulation": {
            "country": "US",
            "title": "FDA Regulation on E-cigarettes",
            "effective_date": "2025-06-01",
            "regulation_id": new_regulation_id,
        },
        "change_detection_results": change_state.get("change_detection_results", []),
        "change_summary": change_summary,
        "change_detection": {"terminated": False},
        "validation_retry_count": 0,
    }

    try:
        # LangGraph 실행 (detect_changes부터 시작)
        final_state = await app.ainvoke(initial_state, config={"configurable": {}})
        logger.info("✅ 파이프라인 실행 완료")

    except Exception as e:
        logger.error(f"❌ 파이프라인 실행 실패: {e}", exc_info=True)
        return

    # 7. 결과 출력
    logger.info("\n[Step 7] 실행 결과 요약")
    logger.info("=" * 80)

    logger.info(f"\n🔍 변경 감지:")
    logger.info(f"  - 상태: {change_summary.get('status')}")
    logger.info(f"  - 변경 건수: {change_summary.get('total_changes', 0)}")
    logger.info(f"  - 고신뢰도: {change_summary.get('high_confidence_changes', 0)}")
    
    # 변경 감지 상세 결과
    change_results = final_state.get("change_detection_results", [])
    if change_results:
        logger.info(f"\n  📝 변경 상세:")
        for idx, result in enumerate(change_results[:5], 1):
            if result.get("change_detected"):
                logger.info(f"    {idx}. [{result.get('section_ref')}] {result.get('change_type')} - {result.get('confidence_level')}")

    mapping = final_state.get("mapping", {})
    mapping_items = mapping.get("items", [])
    logger.info(f"\n🔗 제품-규제 매핑:")
    logger.info(f"  - 매핑 항목: {len(mapping_items)}개")
    applies_count = sum(1 for item in mapping_items if item.get("applies"))
    logger.info(f"  - 적용 대상: {applies_count}개")

    strategies = final_state.get("strategies", [])
    logger.info(f"\n💡 대응 전략:")
    logger.info(f"  - 전략 개수: {len(strategies)}개")
    for i, strategy in enumerate(strategies[:3], 1):
        logger.info(f"  {i}. {strategy[:80]}...")

    impact_scores = final_state.get("impact_scores", [])
    if impact_scores:
        impact = impact_scores[0]
        logger.info(f"\n📊 영향도 평가:")
        logger.info(f"  - 영향도: {impact.get('impact_level')}")
        logger.info(f"  - 점수: {impact.get('weighted_score'):.2f}")

    report = final_state.get("report", {})
    if report:
        logger.info(f"\n📋 최종 리포트:")
        logger.info(f"  - 생성 시각: {report.get('generated_at')}")
        logger.info(f"  - 섹션 수: {len(report.get('sections', []))}")
        logger.info(f"  - Report ID: {report.get('report_id')}")

    logger.info("\n" + "=" * 80)
    logger.info("🎉 전체 파이프라인 실행 완료!")
    logger.info("=" * 80)
    
    # 디버그: change_detected vs confidence_level 불일치 검사
    mismatch = [r for r in change_results if not r.get("change_detected") and r.get("confidence_level") == "HIGH"]
    if mismatch:
        logger.warning(f"\n⚠️ 경고: change_detected=False이지만 confidence_level=HIGH인 경우 {len(mismatch)}건 발견")
        for r in mismatch[:3]:
            logger.warning(f"  - Section: {r.get('section_ref')}, Type: {r.get('change_type')}")

    return final_state


async def main():
    await run_full_pipeline()

    # 결과는 run_full_pipeline 내부에서 출력
    if False:  # 사용 안 함
        # 결과 요약 출력
        preprocess_results = final_state.get("preprocess_results", [])
        change_summary = final_state.get("change_summary", {})
        mapping_items = final_state.get("mapping", {}).get("items", [])

        logger.info("\n[Step 5] 실행 결과 요약")
        logger.info("=" * 80)

        # 전처리 결과
        logger.info("\n📄 전처리:")
        if preprocess_results:
            logger.info(f"  - 상태: {preprocess_results[0].get('status')}")
            logger.info(
                f"  - 처리 페이지: {len(preprocess_results[0].get('vision_extraction_result', []))}"
            )
        else:
            logger.info("  - 결과 없음")

        # Change Detection 결과
        logger.info("\n🔍 변경 감지:")
        logger.info(f"  - 상태: {change_summary.get('status', 'unknown')}")
        changes = final_state.get("change_detection_results", [])
        logger.info(f"  - 변경 건수: {len(changes)}")

        # Mapping 결과
        logger.info("\n🔗 제품-규제 매핑:")
        logger.info(f"  - 매핑 항목: {len(mapping_items)}개")
        applies_count = sum(1 for item in mapping_items if item.get("applies"))
        logger.info(f"  - 적용 대상: {applies_count}개")

        # Strategy 결과
        strategies = final_state.get("strategies", [])
        logger.info(f"\n💡 대응 전략:")
        logger.info(f"  - 전략 개수: {len(strategies)}개")
        for i, strategy in enumerate(strategies[:3], 1):
            logger.info(f"  {i}. {strategy[:80]}...")

        # Impact Score 결과
        impact_scores = final_state.get("impact_scores", [])
        if impact_scores:
            impact = impact_scores[0]
            logger.info(f"\n📊 영향도 평가:")
            logger.info(f"  - 영향도: {impact.get('impact_level')}")
            logger.info(f"  - 점수: {impact.get('weighted_score'):.2f}")

        # Report 결과
        report = final_state.get("report", {})
        if report:
            logger.info(f"\n📋 최종 리포트:")
            logger.info(f"  - 생성 시각: {report.get('generated_at')}")
            logger.info(f"  - 섹션 수: {len(report.get('sections', []))}")
            logger.info(f"  - Report ID: {report.get('report_id')}")

        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
