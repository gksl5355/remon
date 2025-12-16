"""
module: run_pipeline_clean.py
description: REMON AI Pipeline 클린 실행 스크립트 (하드코딩 제거, 그래프/State 기반 자동 실행)
author: AI Agent
created: 2025-01-21
updated: 2025-01-21
dependencies:
    - app.ai_pipeline.graph
    - app.ai_pipeline.state

실행 방법:
    # 단일 제품 처리
    python scripts/run_pipeline_clean.py --pdf /tmp/Regulation_Data_B.pdf --product-id 1
    
    # 전체 제품 처리
    python scripts/run_pipeline_clean.py --pdf /tmp/Regulation_Data_B.pdf --all-products
    
    # S3 자동 로드
    python scripts/run_pipeline_clean.py --s3-date 20250121 --all-products
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f'logs/clean_pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
    ],
)
logger = logging.getLogger(__name__)


def print_summary(state: AppState):
    """파이프라인 결과 요약 출력."""
    logger.info("\n" + "=" * 80)
    logger.info("📋 파이프라인 실행 결과")
    logger.info("=" * 80)
    
    # 전처리
    preprocess_summary = state.get("preprocess_summary", {})
    if preprocess_summary:
        logger.info(f"\n📄 전처리: {preprocess_summary.get('status')}")
        logger.info(f"  - 성공: {preprocess_summary.get('succeeded', 0)}개")
    
    # 변경 감지
    change_summary = state.get("change_summary", {})
    if change_summary:
        logger.info(f"\n🔍 변경 감지: {change_summary.get('status')}")
        logger.info(f"  - 변경: {change_summary.get('total_changes', 0)}개")
        logger.info(f"  - 고신뢰도: {change_summary.get('high_confidence_changes', 0)}개")
    
    # 임베딩
    dual_index = state.get("dual_index_summary", {})
    if dual_index:
        logger.info(f"\n📦 임베딩: {dual_index.get('qdrant_chunks', 0)}개 청크")
    
    # 매핑
    mapping = state.get("mapping", {})
    if mapping:
        items = mapping.get("items", [])
        applies = sum(1 for item in items if item.get("applies"))
        logger.info(f"\n🔗 매핑: {len(items)}개 항목 ({applies}개 적용)")
    
    # 전략
    strategies = state.get("strategies", [])
    if strategies:
        logger.info(f"\n💡 전략: {len(strategies)}개")
    
    # 영향도
    impact_scores = state.get("impact_scores", [])
    if impact_scores:
        impact = impact_scores[0]
        logger.info(f"\n📊 영향도: {impact.get('impact_level')} ({impact.get('weighted_score', 0):.2f})")
    
    # 리포트
    report = state.get("report", {})
    if report:
        logger.info(f"\n📋 리포트: {len(report.get('sections', []))}개 섹션")
    
    logger.info("\n" + "=" * 80)


async def fetch_product_ids() -> list[int]:
    """DB에서 전체 제품 ID 조회."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT product_id FROM products ORDER BY product_id")
        )
        return [row[0] for row in result.fetchall()]


async def run_single_product(pdf_path: str, product_id: int):
    """단일 제품 파이프라인 실행."""
    logger.info("=" * 80)
    logger.info(f"🚀 단일 제품 파이프라인 실행 (product_id={product_id})")
    logger.info("=" * 80)
    
    # 초기 State (최소한의 설정만)
    state: AppState = {
        "preprocess_request": {
            "pdf_paths": [pdf_path],
            "use_vision_pipeline": True,
        },
        "change_context": {},  # 비어있음 → change_detection_node가 자동 처리
        "mapping_filters": {"product_id": product_id},
    }
    
    # 그래프 실행 (start_node 지정 안 함 = "preprocess")
    app = build_graph()
    
    try:
        final_state = await app.ainvoke(state)
        logger.info(f"✅ 제품 {product_id} 파이프라인 완료")
        print_summary(final_state)
        return final_state
    except Exception as e:
        logger.error(f"❌ 제품 {product_id} 파이프라인 실패: {e}", exc_info=True)
        return None


async def run_all_products(pdf_path: str):
    """전체 제품 파이프라인 실행 (전처리 1회 재사용)."""
    logger.info("=" * 80)
    logger.info("🚀 전체 제품 파이프라인 실행")
    logger.info("=" * 80)
    
    # Step 1: 전처리 + 변경 감지 1회 실행
    logger.info("\n[Step 1] 전처리 + 변경 감지 (1회)")
    
    from app.ai_pipeline.preprocess import preprocess_node
    from app.ai_pipeline.nodes.change_detection import change_detection_node
    from app.ai_pipeline.nodes.embedding import embedding_node
    
    base_state: AppState = {
        "preprocess_request": {
            "pdf_paths": [pdf_path],
            "use_vision_pipeline": True,
        },
        "change_context": {},  # 비어있음 → 자동 처리
    }
    
    # 전처리
    base_state = await preprocess_node(base_state)
    
    # 변경 감지
    base_state = await change_detection_node(base_state)
    
    # 임베딩 (필요 시)
    if base_state.get("needs_embedding"):
        logger.info("📦 임베딩 실행")
        base_state = await embedding_node(base_state)
    else:
        logger.info("📦 임베딩 스킵 (변경 없음)")
    
    # Step 2: 제품 목록 조회
    logger.info("\n[Step 2] 제품 목록 조회")
    product_ids = await fetch_product_ids()
    logger.info(f"  ✅ {len(product_ids)}개 제품 발견")
    
    if not product_ids:
        logger.error("❌ 제품이 없습니다")
        return
    
    # Step 3: 제품별 매핑/전략/리포트 실행
    logger.info("\n[Step 3] 제품별 파이프라인 실행")
    
    # map_products부터 시작하는 그래프
    app = build_graph(start_node="map_products")
    
    import copy
    results = []
    
    for pid in product_ids:
        logger.info(f"\n▶️ 제품 {pid} 처리 중...")
        
        # State 복사 (전처리 결과 재사용)
        per_product_state = copy.deepcopy(base_state)
        per_product_state["mapping_filters"] = {"product_id": pid}
        
        # validation_retry_count 누적 유지
        if results:
            last_retry = results[-1].get("validation_retry_count", 0)
            per_product_state["validation_retry_count"] = last_retry
        else:
            per_product_state["validation_retry_count"] = 0
        
        try:
            final_state = await app.ainvoke(per_product_state)
            logger.info(f"✅ 제품 {pid} 완료")
            results.append(final_state)
        except Exception as e:
            logger.error(f"❌ 제품 {pid} 실패: {e}")
            continue
    
    # Step 4: 전체 결과 요약
    logger.info("\n[Step 4] 전체 결과 요약")
    logger.info(f"  - 처리: {len(results)}/{len(product_ids)}개 제품")
    logger.info(f"  - 성공: {len(results)}개")
    logger.info(f"  - 실패: {len(product_ids) - len(results)}개")
    
    if results:
        logger.info("\n마지막 제품 상세:")
        print_summary(results[-1])
    
    return results


async def run_s3_auto_load(s3_date: str | None, product_id: int | None):
    """S3 자동 로드 + 파이프라인 실행."""
    logger.info("=" * 80)
    logger.info("🚀 S3 자동 로드 파이프라인")
    logger.info("=" * 80)
    
    # 초기 State
    state: AppState = {
        "preprocess_request": {
            "load_from_s3": True,
            "s3_date": s3_date,  # YYYYMMDD or None (오늘)
            "use_vision_pipeline": True,
        },
        "change_context": {},
    }
    
    # 단일 제품 또는 전체 제품
    if product_id:
        state["mapping_filters"] = {"product_id": product_id}
    
    # 그래프 실행
    app = build_graph()
    
    try:
        final_state = await app.ainvoke(state)
        logger.info("✅ S3 자동 로드 파이프라인 완료")
        print_summary(final_state)
        return final_state
    except Exception as e:
        logger.error(f"❌ S3 자동 로드 실패: {e}", exc_info=True)
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="REMON AI Pipeline 클린 실행 (하드코딩 제거)"
    )
    
    # 실행 모드
    parser.add_argument(
        "--mode",
        choices=["single", "all", "s3"],
        default="single",
        help="실행 모드: single (단일 제품), all (전체 제품), s3 (S3 자동 로드)",
    )
    
    # PDF 설정
    parser.add_argument(
        "--pdf",
        default="/tmp/Regulation_Data_B.pdf",
        help="로컬 PDF 경로 (mode=single/all)",
    )
    
    # 제품 설정
    parser.add_argument(
        "--product-id",
        type=int,
        help="제품 ID (mode=single)",
    )
    
    parser.add_argument(
        "--all-products",
        action="store_true",
        help="전체 제품 처리 (mode=all과 동일)",
    )
    
    # S3 설정
    parser.add_argument(
        "--s3-date",
        help="S3 날짜 (YYYYMMDD, mode=s3)",
    )
    
    args = parser.parse_args()
    
    # 모드 자동 결정
    if args.all_products:
        args.mode = "all"
    
    # 실행
    if args.mode == "single":
        if not args.product_id:
            logger.error("❌ --product-id 필수 (단일 제품 모드)")
            return
        await run_single_product(args.pdf, args.product_id)
    
    elif args.mode == "all":
        await run_all_products(args.pdf)
    
    elif args.mode == "s3":
        await run_s3_auto_load(args.s3_date, args.product_id)


if __name__ == "__main__":
    asyncio.run(main())
