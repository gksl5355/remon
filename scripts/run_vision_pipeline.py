#!/usr/bin/env python
"""
Vision-Centric Preprocessing Pipeline 실행 스크립트

Usage:
    uv run python scripts/run_vision_pipeline.py
    uv run python scripts/run_vision_pipeline.py --pdf demo/1.pdf --enable-graph
"""

import asyncio
import logging
import argparse
from pathlib import Path
import sys
from datetime import datetime
import os

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.ai_pipeline.preprocess.config import PreprocessConfig
from app.ai_pipeline.preprocess.vision_orchestrator import VisionOrchestrator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# 출력 저장 디렉토리
OUTPUT_DIR = project_root / "data" / "vision_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Vision Pipeline 실행")
    parser.add_argument(
        "--pdf",
        type=str,
        help="처리할 PDF 파일 경로 (지정 안하면 demo 폴더 전체)",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="app/ai_pipeline/preprocess/demo",
        help="처리할 PDF 폴더 경로 (기본: demo)",
    )
    parser.add_argument(
        "--enable-graph", action="store_true", help="지식 그래프 추출 활성화"
    )
    parser.add_argument(
        "--disable-langsmith", action="store_true", help="LangSmith 추적 비활성화"
    )
    parser.add_argument(
        "--save-outputs",
        action="store_true",
        default=True,
        help="LLM 출력을 .txt로 저장 (기본: True)",
    )
    # 병렬 처리 설정
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=3,
        help="최대 동시 실행 수 (기본값: 3)",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=None,
        help="토큰 예산 (기본값: None, 제한 없음)",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=120,
        help="API 요청 타임아웃 초 (기본값: 120)",
    )
    parser.add_argument(
        "--retry-max-attempts",
        type=int,
        default=2,
        help="최대 재시도 횟수 (기본값: 2)",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=1.0,
        help="재시도 대기 시간 초 (기본값: 1.0)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="병렬 처리 비활성화 (순차 처리)",
    )
    parser.add_argument(
        "--skip-indexing",
        action="store_true",
        help="Qdrant 저장 건너뛰기 (콘솔 출력만)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Qdrant 컬렉션명 (기본값: .env의 QDRANT_COLLECTION)",
    )
    return parser.parse_args()


def save_llm_outputs(result: dict, pdf_name: str, timestamp: str) -> None:
    """LLM 출력을 .txt 파일로 저장."""
    if result["status"] != "success":
        return

    vision_results = result.get("vision_extraction_result", [])
    
    # 파일명 길이 제한 (80글자)
    safe_pdf_name = pdf_name[:80] if len(pdf_name) > 80 else pdf_name

    for page_result in vision_results:
        page_num = page_result["page_num"]
        structure = page_result["structure"]
        markdown_content = structure["markdown_content"]
        model_used = page_result["model_used"]

        # 파일명: {pdf_name}_page{num}_{model}_{timestamp}.txt
        filename = f"{safe_pdf_name}_page{page_num:03d}_{model_used}_{timestamp}.txt"
        output_path = OUTPUT_DIR / filename

        # 메타데이터 포함 저장
        content = f"""# Vision LLM Output
# PDF: {pdf_name}
# Page: {page_num}
# Model: {model_used}
# Complexity: {page_result['complexity_score']:.2f}
# Has Table: {page_result['has_table']}
# Tokens Used: {page_result.get('tokens_used', 0)}
# Timestamp: {timestamp}

{markdown_content}
"""

        output_path.write_text(content, encoding="utf-8")

    logger.info(f"💾 LLM 출력 저장 완료: {OUTPUT_DIR} ({len(vision_results)}개 파일)")


async def process_single_pdf(pdf_path: Path, args, orchestrator) -> dict:
    """단일 PDF 처리."""
    pdf_name = pdf_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 60)
    logger.info(f"🚀 처리 시작: {pdf_path.name}")
    logger.info("=" * 60)

    # 병렬 처리 여부 설정
    use_parallel = not args.no_parallel
    result = await asyncio.to_thread(orchestrator.process_pdf, str(pdf_path), use_parallel)

    # 테스트 모드: 콘솔에 상세 결과 출력
    if args.skip_indexing and result["status"] == "success":
        _print_detailed_results(result)

    # LLM 출력 저장
    if args.save_outputs and result["status"] == "success":
        save_llm_outputs(result, pdf_name, timestamp)

    # 결과 출력
    if result["status"] == "success":
        vision_results = result.get("vision_extraction_result", [])
        index_summary = result.get("dual_index_summary", {})
        
        gpt4o_count = sum(1 for p in vision_results if p.get("model_used") == "gpt-4o")
        total_tokens = sum(p.get("tokens_used", 0) for p in vision_results)

        if args.skip_indexing:
            logger.info(f"✅ 완료: {len(vision_results)}페이지, {total_tokens:,}토큰 (Qdrant 저장 건너뜀)")
        else:
            logger.info(f"✅ 완료: {len(vision_results)}페이지, {index_summary.get('qdrant_chunks', 0)}청크, {total_tokens:,}토큰")
    else:
        logger.error(f"❌ 실패: {result.get('error')}")
    
    return result


def _print_detailed_results(result: dict) -> None:
    """테스트 모드: 콘솔에 상세 결과 출력."""
    vision_results = result.get("vision_extraction_result", [])
    processing_results = result.get("processing_results", {})
    chunks = processing_results.get("chunks", [])
    
    logger.info("\n" + "=" * 60)
    logger.info("📄 Vision 추출 결과 상세")
    logger.info("=" * 60)
    
    for page_result in vision_results:
        page_num = page_result["page_num"]
        model = page_result["model_used"]
        complexity = page_result["complexity_score"]
        tokens = page_result.get("tokens_used", 0)
        structure = page_result["structure"]
        markdown = structure.get("markdown_content", "")
        
        logger.info(f"\n[페이지 {page_num}]")
        logger.info(f"  모델: {model}")
        logger.info(f"  복잡도: {complexity:.2f}")
        logger.info(f"  토큰: {tokens:,}")
        logger.info(f"  표 포함: {page_result.get('has_table', False)}")
        logger.info(f"  내용:\n{markdown}")
        logger.info("-" * 60)
    
    if chunks:
        logger.info("\n" + "=" * 60)
        logger.info("📦 청킹 결과 요약")
        logger.info("=" * 60)
        for i, chunk in enumerate(chunks[:10], 1):  # 처음 10개만
            chunk_text = chunk.get("text", chunk.get("content", ""))
            logger.info(f"\n[청크 {i}]")
            logger.info(f"  페이지: {chunk.get('page_num', 'N/A')}")
            logger.info(f"  섹션: {chunk.get('section', 'N/A')}")
            logger.info(f"  내용: {chunk_text[:200]}...")
        if len(chunks) > 10:
            logger.info(f"\n... 외 {len(chunks) - 10}개 청크")


async def main():
    args = parse_args()

    # LangSmith 설정
    if not args.disable_langsmith:
        PreprocessConfig.setup_langsmith()

    # PDF 목록 수집
    pdf_files = []
    
    if args.pdf:
        # 단일 파일 지정
        pdf_path = Path(args.pdf)
        if not pdf_path.is_absolute():
            pdf_path = project_root / pdf_path
        if pdf_path.exists():
            pdf_files = [pdf_path]
        else:
            logger.error(f"❌ PDF 파일 없음: {pdf_path}")
            return
    else:
        # 폴더 전체 처리
        folder_path = Path(args.folder)
        if not folder_path.is_absolute():
            folder_path = project_root / folder_path
        
        if not folder_path.exists():
            logger.error(f"❌ 폴더 없음: {folder_path}")
            return
        
        pdf_files = sorted(folder_path.glob("*.pdf"))
        pdf_files = [p for p in pdf_files if not p.name.startswith(".")]
    
    if not pdf_files:
        logger.error("❌ 처리할 PDF 파일이 없습니다")
        return

    logger.info(f"📚 총 {len(pdf_files)}개 PDF 파일 발견")
    logger.info(f"🔍 지식 그래프: {'활성화' if args.enable_graph else '비활성화'}")
    logger.info(f"💾 출력 저장: {'활성화' if args.save_outputs else '비활성화'}")
    logger.info(f"⚡ 병렬 처리: {'비활성화' if args.no_parallel else f'활성화 (max_concurrency={args.max_concurrency})'}")
    logger.info(f"🗄️  Qdrant 저장: {'건너뛰기 (테스트 모드)' if args.skip_indexing else '활성화'}")

    # Orchestrator 생성 (생성자 인자로 설정 전달)
    orchestrator = VisionOrchestrator(
        max_concurrency=args.max_concurrency,
        token_budget=args.token_budget,
        request_timeout=args.request_timeout,
        retry_max_attempts=args.retry_max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        enable_graph=args.enable_graph,
    )
    
    # 컬렉션명 설정
    if args.collection:
        from app.ai_pipeline.preprocess.semantic_processing import DualIndexer
        orchestrator.dual_indexer = DualIndexer(collection_name=args.collection)
        logger.info(f"🗄️  Qdrant 컬렉션: {args.collection}")
    else:
        logger.info(f"🗄️  Qdrant 컬렉션: {os.getenv('QDRANT_COLLECTION', 'remon_regulations')}")
    
    # 테스트 모드: Qdrant 저장 건너뛰기 (스크립트 레벨에서만 처리)
    if args.skip_indexing:
        from unittest.mock import MagicMock
        # DualIndexer를 Mock으로 교체
        orchestrator.dual_indexer = MagicMock()
        orchestrator.dual_indexer.index = lambda chunks, graph_data, source_file: {
            "status": "skipped",
            "qdrant_chunks": 0,
            "graph_nodes": len(graph_data.get("nodes", [])),
            "graph_edges": len(graph_data.get("edges", [])),
            "collection_name": "test_mode",
            "processed_at": "test_mode",
            "message": "Indexing skipped for testing"
        }

    # 순차 처리
    results = []
    for idx, pdf_path in enumerate(pdf_files, 1):
        logger.info(f"\n[{idx}/{len(pdf_files)}] {pdf_path.name}")
        result = await process_single_pdf(pdf_path, args, orchestrator)
        results.append({"file": pdf_path.name, "status": result["status"]})

    # 전체 요약
    logger.info("\n" + "=" * 60)
    logger.info("📊 전체 처리 완료")
    logger.info("=" * 60)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    logger.info(f"성공: {success_count}/{len(results)}")
    
    if success_count < len(results):
        logger.info("\n실패 파일:")
        for r in results:
            if r["status"] != "success":
                logger.info(f"  - {r['file']}")
    
    if args.save_outputs:
        logger.info(f"\n📁 출력 위치: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
