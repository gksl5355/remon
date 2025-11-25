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

    result = await asyncio.to_thread(orchestrator.process_pdf, str(pdf_path))

    # LLM 출력 저장
    if args.save_outputs and result["status"] == "success":
        save_llm_outputs(result, pdf_name, timestamp)

    # 결과 출력
    if result["status"] == "success":
        vision_results = result.get("vision_extraction_result", [])
        index_summary = result.get("dual_index_summary", {})
        
        gpt4o_count = sum(1 for p in vision_results if p.get("model_used") == "gpt-4o")
        total_tokens = sum(p.get("tokens_used", 0) for p in vision_results)

        logger.info(f"✅ 완료: {len(vision_results)}페이지, {index_summary.get('qdrant_chunks', 0)}청크, {total_tokens:,}토큰")
    else:
        logger.error(f"❌ 실패: {result.get('error')}")
    
    return result


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

    # Orchestrator 생성
    orchestrator = VisionOrchestrator()
    if args.enable_graph:
        orchestrator.enable_graph = True

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
