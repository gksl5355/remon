#!/usr/bin/env python
"""
Vision Pipeline + Change Detection 통합 실행 스크립트

Usage:
    # Vision Pipeline만 실행
    uv run python scripts/run_vision_pipeline\ copy.py --pdf demo/1.pdf

    # Vision Pipeline + Change Detection 실행
    uv run python scripts/run_vision_pipeline\ copy.py --pdf demo/new_regulation.pdf --enable-change-detection --legacy-id FDA-2024-001

    # 컬렉션 초기화 후 실행
    uv run python scripts/run_vision_pipeline\ copy.py --pdf demo/1.pdf --reset-collection
"""

import asyncio
import logging
import argparse
from pathlib import Path
import sys
from datetime import datetime
import os
from typing import Optional

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
        default=30,
        help="최대 동시 실행 수 (기본값: 30)",
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
    parser.add_argument(
        "--reset-collection",
        action="store_true",
        help="기존 컬렉션 삭제 후 재생성",
    )
    parser.add_argument(
        "--enable-change-detection",
        action="store_true",
        help="변경 감지 활성화",
    )
    parser.add_argument(
        "--legacy-id",
        type=str,
        default=None,
        help="Legacy 규제 ID (변경 감지 시 필요, 예: FDA-2024-001)",
    )
    parser.add_argument(
        "--legacy-file",
        type=str,
        default=None,
        help="Legacy 전처리 JSON 파일 경로 (파일 기반 비교용)",
    )
    parser.add_argument(
        "--compare-jsons",
        action="store_true",
        help="기존 JSON 파일 2개를 직접 비교 (Vision Pipeline 생략)",
    )
    parser.add_argument(
        "--new-json",
        type=str,
        default=None,
        help="신규 규제 JSON 파일 경로 (--compare-jsons 사용 시)",
    )
    parser.add_argument(
        "--legacy-json",
        type=str,
        default=None,
        help="Legacy 규제 JSON 파일 경로 (--compare-jsons 사용 시)",
    )
    parser.add_argument(
        "--save-preprocessed",
        action="store_true",
        help="전처리 결과를 JSON으로 저장 (demo 폴더)",
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


def save_preprocessed_data(result: dict, pdf_path: Path, output_dir: Path) -> Optional[Path]:
    """전처리 결과를 JSON으로 저장 (변경 감지용)."""
    import json

    if result["status"] != "success":
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # 파일명: {pdf_name}_preprocessed.json
    output_file = output_dir / f"{pdf_path.stem}_preprocessed.json"

    # 저장할 데이터 구성
    preprocessed_data = {
        "source_pdf": pdf_path.name,
        "processed_at": datetime.now().isoformat(),
        "vision_extraction_result": result.get("vision_extraction_result", []),
        "graph_data": result.get("graph_data", {}),
        "dual_index_summary": result.get("dual_index_summary", {}),
    }

    output_file.write_text(
        json.dumps(preprocessed_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"💾 전처리 데이터 저장: {output_file}")

    return output_file


async def process_single_pdf(pdf_path: Path, args, orchestrator) -> dict:
    """단일 PDF 처리 (Vision Pipeline + S3 업로드 + 선택적 Change Detection)."""
    pdf_name = pdf_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("=" * 60)
    logger.info(f"🚀 처리 시작: {pdf_path.name}")
    logger.info("=" * 60)

    # 전처리 JSON 파일 확인
    import json
    demo_dir = project_root / "app" / "ai_pipeline" / "preprocess" / "demo"
    preprocessed_file = demo_dir / f"{pdf_path.stem}_preprocessed.json"
    
    # S3 클라이언트 초기화
    from app.utils.s3_client import S3Client
    s3_client = S3Client()
    
    if preprocessed_file.exists():
        logger.info(f"📂 전처리 JSON 파일 발견: {preprocessed_file.name}")
        logger.info("⏩ Vision Pipeline 생략, JSON에서 로드")
        
        preprocessed_data = json.loads(preprocessed_file.read_text(encoding="utf-8"))
        result = {
            "status": "success",
            "vision_extraction_result": preprocessed_data.get("vision_extraction_result", []),
            "graph_data": preprocessed_data.get("graph_data", {}),
            "dual_index_summary": preprocessed_data.get("dual_index_summary", {})
        }
        logger.info(f"✅ 전처리 데이터 로드 완료: {len(result['vision_extraction_result'])}페이지")
    else:
        logger.info("🔄 Vision Pipeline 실행")
        
        # Phase 1: Vision Pipeline 실행 (Prompt Caching을 위해 순차 처리 강제)
        use_parallel = not args.no_parallel
        if use_parallel:
            logger.warning("⚠️  Prompt Caching 활성화를 위해 순차 처리로 전환합니다.")
            use_parallel = False
        result = await asyncio.to_thread(
            orchestrator.process_pdf, str(pdf_path), use_parallel
        )

        if result["status"] != "success":
            logger.error(f"❌ Vision Pipeline 실패: {result.get('error')}")
            return result

        # LLM 출력 저장
        if args.save_outputs:
            save_llm_outputs(result, pdf_name, timestamp)

        # 전처리 데이터 저장 (demo 폴더 + S3)
        if args.save_preprocessed:
            saved_json = save_preprocessed_data(result, pdf_path, demo_dir)
            
            # S3 업로드
            if saved_json:
                try:
                    s3_key = s3_client.upload_json(str(saved_json))
                    logger.info(f"🌐 S3 업로드 완료: {s3_key}")
                except Exception as e:
                    logger.error(f"❌ S3 업로드 실패: {e}")

    # Phase 2: Change Detection (선택적)
    if args.enable_change_detection:
        logger.info("\n" + "=" * 60)
        logger.info("🔍 변경 감지 시작")
        logger.info("=" * 60)

        from app.ai_pipeline.preprocess import preprocess_node
        from app.ai_pipeline.state import AppState
        import json

        # Legacy 데이터 로드 (파일 기반 비교)
        legacy_vision_results = None
        if args.legacy_file:
            legacy_path = Path(args.legacy_file)
            if not legacy_path.is_absolute():
                legacy_path = project_root / legacy_path

            if legacy_path.exists():
                legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
                legacy_vision_results = legacy_data.get("vision_extraction_result", [])
                logger.info(f"📂 Legacy 파일 로드: {legacy_path.name}")
            else:
                logger.warning(f"⚠️ Legacy 파일 없음: {legacy_path}")

        # AppState 구성
        state: AppState = {
            "preprocess_request": {
                "pdf_paths": [str(pdf_path)],
                "use_vision_pipeline": True,
                "enable_change_detection": True,
            },
            "vision_extraction_result": result.get("vision_extraction_result", []),
            "graph_data": result.get("graph_data", {}),
            "dual_index_summary": result.get("dual_index_summary", {}),
            "change_context": (
                {
                    "legacy_regulation_id": args.legacy_id,
                    "legacy_vision_results": legacy_vision_results,
                }
                if args.legacy_id or legacy_vision_results
                else {}
            ),
        }

        # Change Detection 실행
        try:
            from app.ai_pipeline.nodes.change_detection import change_detection_node

            state = await change_detection_node(state)

            # 변경 감지 결과 추가
            result["change_detection_results"] = state.get(
                "change_detection_results", []
            )
            result["change_summary"] = state.get("change_summary", {})

            # 변경 감지 결과 출력
            _print_change_detection_results(state)

        except Exception as e:
            logger.error(f"❌ 변경 감지 실패: {e}", exc_info=True)
            result["change_detection_error"] = str(e)

    # 결과 출력
    vision_results = result.get("vision_extraction_result", [])
    index_summary = result.get("dual_index_summary", {})
    total_tokens = sum(p.get("tokens_used", 0) for p in vision_results)

    if args.skip_indexing:
        logger.info(
            f"\n✅ 완료: {len(vision_results)}페이지, {total_tokens:,}토큰 (Qdrant 저장 건너뜀)"
        )
    else:
        logger.info(
            f"\n✅ 완료: {len(vision_results)}페이지, {index_summary.get('qdrant_chunks', 0)}청크, {total_tokens:,}토큰"
        )

    return result


async def main():
    args = parse_args()

    # LangSmith 설정
    if not args.disable_langsmith:
        PreprocessConfig.setup_langsmith()

    # JSON 직접 비교 모드
    if args.compare_jsons:
        await compare_json_files(args)
        return

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
    logger.info(
        f"⚡ 병렬 처리: {'비활성화' if args.no_parallel else f'활성화 (max_concurrency={args.max_concurrency})'}"
    )
    logger.info(
        f"🗄️  Qdrant 저장: {'건너뛰기 (테스트 모드)' if args.skip_indexing else '활성화'}"
    )
    logger.info(
        f"🔄 변경 감지: {'활성화' if args.enable_change_detection else '비활성화'}"
    )
    logger.info(
        f"💾 전처리 데이터 저장: {'활성화' if args.save_preprocessed else '비활성화'}"
    )
    if args.enable_change_detection:
        if args.legacy_id:
            logger.info(f"📋 Legacy 규제 ID: {args.legacy_id}")
        if args.legacy_file:
            logger.info(f"📂 Legacy 파일: {args.legacy_file}")

    # 컬렉션명 설정
    collection_name = args.collection or os.getenv(
        "QDRANT_COLLECTION", "skala-2.4.17-regulation"
    )

    # Orchestrator 생성
    orchestrator = VisionOrchestrator(
        max_concurrency=args.max_concurrency,
        token_budget=args.token_budget,
        request_timeout=args.request_timeout,
        retry_max_attempts=args.retry_max_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
        enable_graph=args.enable_graph,
    )

    # 컬렉션명 설정
    if args.collection and not args.skip_indexing:
        from app.ai_pipeline.preprocess.semantic_processing import DualIndexer

        orchestrator.dual_indexer = DualIndexer(collection_name=args.collection)
        logger.info(f"🗄️  Qdrant 컬렉션: {args.collection}")
    else:
        logger.info(f"🗄️  Qdrant 컬렉션: {collection_name}")

    # 테스트 모드: Qdrant 저장 건너뛰기
    if args.skip_indexing:
        from unittest.mock import MagicMock

        orchestrator.dual_indexer = MagicMock()
        orchestrator.dual_indexer.index = lambda chunks, graph_data, source_file, regulation_id=None, vision_results=None: {
            "status": "skipped",
            "qdrant_chunks": 0,
            "reference_blocks_count": 0,
            "graph_nodes": len(graph_data.get("nodes", [])),
            "graph_edges": len(graph_data.get("edges", [])),
            "collection_name": "test_mode",
            "processed_at": "test_mode",
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


async def compare_json_files(args) -> None:
    """기존 JSON 파일 2개를 직접 비교 (Vision Pipeline 생략)."""
    import json
    from app.ai_pipeline.nodes.change_detection import change_detection_node
    from app.ai_pipeline.state import AppState

    if not args.new_json or not args.legacy_json:
        logger.error("❌ --new-json과 --legacy-json 필수")
        return

    # JSON 파일 로드
    new_path = Path(args.new_json)
    legacy_path = Path(args.legacy_json)

    if not new_path.is_absolute():
        new_path = project_root / new_path
    if not legacy_path.is_absolute():
        legacy_path = project_root / legacy_path

    if not new_path.exists():
        logger.error(f"❌ 신규 JSON 없음: {new_path}")
        return
    if not legacy_path.exists():
        logger.error(f"❌ Legacy JSON 없음: {legacy_path}")
        return

    logger.info("=" * 60)
    logger.info("🔍 JSON 비교 모드")
    logger.info("=" * 60)
    logger.info(f"신규: {new_path.name}")
    logger.info(f"Legacy: {legacy_path.name}")

    new_data = json.loads(new_path.read_text(encoding="utf-8"))
    legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))

    new_vision = new_data.get("vision_extraction_result", [])
    legacy_vision = legacy_data.get("vision_extraction_result", [])

    logger.info(f"신규: {len(new_vision)}페이지")
    logger.info(f"Legacy: {len(legacy_vision)}페이지")

    # regulation_id 추출
    new_metadata = new_vision[0].get("structure", {}).get("metadata", {}) if new_vision else {}
    legacy_metadata = legacy_vision[0].get("structure", {}).get("metadata", {}) if legacy_vision else {}

    new_id = f"{new_metadata.get('regulation_type', 'REG')}-{new_metadata.get('country', 'US')}-{new_path.stem}"
    legacy_id = f"{legacy_metadata.get('regulation_type', 'REG')}-{legacy_metadata.get('country', 'US')}-{legacy_path.stem}"

    logger.info(f"\n신규 ID: {new_id}")
    logger.info(f"Legacy ID: {legacy_id}")

    # AppState 구성
    state: AppState = {
        "vision_extraction_result": new_vision,
        "change_context": {
            "new_regulation_id": new_id,
            "legacy_regulation_id": legacy_id,
            "legacy_vision_results": legacy_vision,  # 직접 제공
        },
    }

    # 변경 감지 실행
    logger.info("\n" + "=" * 60)
    logger.info("🔍 변경 감지 실행")
    logger.info("=" * 60)

    try:
        state = await change_detection_node(state)
        _print_change_detection_results(state)
    except Exception as e:
        logger.error(f"❌ 변경 감지 실패: {e}", exc_info=True)


def _print_change_detection_results(state: dict) -> None:
    """변경 감지 결과 출력."""
    change_summary = state.get("change_summary", {})
    change_results = state.get("change_detection_results", [])

    logger.info("\n" + "=" * 60)
    logger.info("📊 변경 감지 요약")
    logger.info("=" * 60)
    logger.info(f"상태: {change_summary.get('status')}")
    logger.info(f"총 Reference Blocks: {change_summary.get('total_reference_blocks', 0)}개")
    logger.info(f"변경 감지: {change_summary.get('total_changes', 0)}개")
    logger.info(f"HIGH 신뢰도: {change_summary.get('high_confidence_changes', 0)}개")
    logger.info(f"Legacy ID: {change_summary.get('legacy_regulation_id', 'N/A')}")
    logger.info(f"신규 ID: {change_summary.get('new_regulation_id', 'N/A')}")

    if not change_results:
        logger.info("\n변경 사항 없음")
        return

    logger.info("\n" + "=" * 60)
    logger.info("🔍 변경 감지 상세 결과")
    logger.info("=" * 60)

    changes_found = [r for r in change_results if r.get("change_detected")]
    
    for i, result in enumerate(changes_found, 1):
        logger.info(f"\n[변경 {i}/{len(changes_found)}] Section {result.get('section_ref')}")
        logger.info(f"  Ref ID: {result.get('new_ref_id')} ↔ {result.get('legacy_ref_id')}")
        logger.info(f"  변경 유형: {result.get('change_type')}")
        logger.info(
            f"  신뢰도: {result.get('confidence_score', 0):.2f} ({result.get('confidence_level')})"
        )
        logger.info(f"  Legacy: {result.get('legacy_snippet', '')[:100]}...")
        logger.info(f"  신규: {result.get('new_snippet', '')[:100]}...")

        # Chain of Thought
        reasoning = result.get("reasoning", {})
        if reasoning:
            logger.info(f"\n  판단 근거:")
            logger.info(
                f"    Step 1: {reasoning.get('step1_context_analysis', '')[:150]}"
            )
            logger.info(
                f"    Step 2: {reasoning.get('step2_term_comparison', '')[:150]}"
            )
            logger.info(
                f"    Step 3: {reasoning.get('step3_semantic_evaluation', '')[:150]}"
            )
            logger.info(
                f"    Step 4: {reasoning.get('step4_final_judgment', '')[:150]}"
            )

        # 수치 변경
        numerical_changes = result.get("numerical_changes", [])
        if numerical_changes:
            logger.info(f"\n  수치 변경:")
            for nc in numerical_changes:
                logger.info(
                    f"    - {nc.get('field')}: {nc.get('legacy_value')} → {nc.get('new_value')}"
                )
                logger.info(f"      맥락: {nc.get('context', 'N/A')}")
                logger.info(f"      영향도: {nc.get('impact')}")
        
        # Adversarial Check
        adv_check = result.get("adversarial_check", {})
        if adv_check:
            logger.info(f"\n  반박 검증:")
            logger.info(f"    반론: {adv_check.get('counter_argument', '')[:100]}")
            logger.info(f"    재반박: {adv_check.get('rebuttal', '')[:100]}")
            logger.info(f"    조정 신뢰도: {adv_check.get('adjusted_confidence', 0):.2f}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"\n❌ 실행 실패: {e}", exc_info=True)
