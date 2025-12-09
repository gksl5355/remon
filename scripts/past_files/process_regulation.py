#!/usr/bin/env python
"""
규제 전처리 및 DB 저장 스크립트

Usage:
    # 1. 기존 규제 전처리 + DB 저장
    uv run python scripts/process_regulation.py --pdf regulation_file/us/old_regulation.pdf --save-to-db
    
    # 2. 신규 규제 전처리 + 변경 감지 + DB 저장 + 임베딩
    uv run python scripts/process_regulation.py --pdf regulation_file/us/new_regulation.pdf --save-to-db --enable-change-detection
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.ai_pipeline.preprocess.vision_orchestrator import VisionOrchestrator
from app.core.database import AsyncSessionLocal
from app.core.repositories.regulation_repository import RegulationRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="규제 전처리 및 DB 저장")
    parser.add_argument("--pdf", type=str, help="S3 키 (regulation/US/file.pdf)")
    parser.add_argument("--date", type=str, help="처리할 날짜 (YYYYMMDD, 기본값: 오늘)")
    parser.add_argument("--save-to-db", action="store_true", help="DB에 저장")
    parser.add_argument("--enable-change-detection", action="store_true", help="변경 감지 활성화")
    parser.add_argument("--max-concurrency", type=int, default=30, help="최대 동시 실행 수")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    from app.utils.s3_client import S3Client
    s3_client = S3Client()
    
    # S3에서 처리할 파일 목록 가져오기
    if args.pdf:
        # 특정 파일 지정
        s3_keys = [args.pdf]
    else:
        # 날짜 기반 자동 탐색
        s3_keys = s3_client.get_today_regulation_files(args.date)
        if not s3_keys:
            logger.error(f"❌ {args.date or 'today'} 규제 파일 없음")
            return
    
    logger.info("=" * 60)
    logger.info(f"🚀 규제 처리 시작: {len(s3_keys)}개 파일")
    logger.info("=" * 60)
    
    for s3_key in s3_keys:
        await process_single_regulation(s3_client, s3_key, args)


async def process_single_regulation(s3_client, s3_key: str, args):
    """S3 규제 파일 1개 처리"""
    logger.info(f"\n📄 처리 중: {s3_key}")
    
    # S3 → /tmp 다운로드
    temp_path = s3_client.download_to_temp(s3_key)
    
    try:
        await _process_pdf(temp_path, s3_key, args)
    finally:
        # 임시 파일 삭제
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"🗑️ 임시 파일 삭제: {temp_path}")


async def _process_pdf(pdf_path: str, s3_key: str, args):
    """PDF 전처리 로직 (기존 코드)"""
    logger.info("=" * 60)
    logger.info(f"🚀 규제 처리 시작: {Path(pdf_path).name}")
    logger.info("=" * 60)
    # Phase 1: Vision Pipeline 실행
    logger.info("📄 Vision Pipeline 실행 중...")
    orchestrator = VisionOrchestrator(max_concurrency=args.max_concurrency)
    
    result = await asyncio.to_thread(
        orchestrator.process_pdf,
        pdf_path,
        use_parallel=True
    )
    
    if result["status"] != "success":
        logger.error(f"❌ Vision Pipeline 실패: {result.get('error')}")
        return
    
    vision_results = result.get("vision_extraction_result", [])
    logger.info(f"✅ Vision Pipeline 완료: {len(vision_results)}페이지")
    
    # Phase 2: DB 저장
    regulation_id = None
    citation_code = None
    if args.save_to_db:
        logger.info("\n💾 PostgreSQL DB 저장 중...")
        
        async with AsyncSessionLocal() as session:
            repo = RegulationRepository()
            
            try:
                regulation = await repo.create_from_vision_result(session, result)
                await session.commit()
                await session.refresh(regulation)
                
                regulation_id = regulation.regulation_id
                citation_code = regulation.citation_code
                
                logger.info(f"✅ DB 저장 완료")
                logger.info(f"   regulation_id: {regulation_id}")
                logger.info(f"   citation_code: {citation_code}")
                logger.info(f"   regul_data 크기: {len(str(regulation.regul_data))} bytes")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ DB 저장 실패: {e}")
                import traceback
                traceback.print_exc()
                return
    
    # Phase 3: 변경 감지 (선택적)
    if args.enable_change_detection and regulation_id:
        logger.info("\n🔍 변경 감지 실행 중...")
        
        async with AsyncSessionLocal() as session:
            from app.ai_pipeline.nodes.change_detection import change_detection_node
            from app.ai_pipeline.state import AppState
            
            # 신규 규제 데이터 조회
            repo = RegulationRepository()
            new_regul_data = await repo.get_regul_data(session, regulation_id)
            
            if not new_regul_data:
                logger.error(f"❌ regulation_id={regulation_id}의 regul_data 조회 실패")
                return
            
            logger.info(f"   신규 규제 데이터 조회 완료: {len(str(new_regul_data))} bytes")
            
            # AppState 구성
            state: AppState = {
                "vision_extraction_result": vision_results,
                "change_context": {
                    "new_regulation_id": regulation_id,
                    # legacy_regulation_id는 자동 탐색됨 (citation_code 기반)
                }
            }
            
            # 변경 감지 실행 (config에 db_session 전달)
            try:
                config = {"configurable": {"db_session": session}}
                state = await change_detection_node(state, config)
                
                change_summary = state.get("change_summary", {})
                change_results = state.get("change_detection_results", [])
                
                logger.info(f"✅ 변경 감지 완료")
                logger.info(f"   상태: {change_summary.get('status')}")
                logger.info(f"   총 변경: {change_summary.get('total_changes', 0)}개")
                logger.info(f"   HIGH 신뢰도: {change_summary.get('high_confidence_changes', 0)}개")
                
                # Legacy regulation_id 출력
                legacy_id = change_summary.get('legacy_regulation_id')
                if legacy_id:
                    logger.info(f"   Legacy regulation_id: {legacy_id}")
                
                # 변경 사항 출력
                if change_results:
                    logger.info("\n📊 주요 변경 사항:")
                    for i, result in enumerate(change_results[:5], 1):
                        if result.get("change_detected"):
                            logger.info(f"   {i}. Section {result.get('section_ref')}")
                            logger.info(f"      유형: {result.get('change_type')}")
                            logger.info(f"      신뢰도: {result.get('confidence_score', 0):.2f}")
                
            except Exception as e:
                logger.error(f"❌ 변경 감지 실패: {e}")
                import traceback
                traceback.print_exc()
    
    # Phase 4: 임베딩 (변경 감지 후 자동 실행됨)
    if args.enable_change_detection:
        logger.info("\n🔢 임베딩은 Vision Pipeline 내부에서 이미 완료됨")
        logger.info(f"   Qdrant 청크: {result.get('dual_index_summary', {}).get('qdrant_chunks', 0)}개")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ 전체 처리 완료")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"\n❌ 실행 실패: {e}", exc_info=True)
