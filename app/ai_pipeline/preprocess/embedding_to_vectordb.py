"""
module: embedding_to_vectordb.py
description: 청크 → 임베딩 생성 → Qdrant VectorDB 저장 (Step 2)
             /data/embeddings의 청크 정보를 읽어서
             임베딩을 생성하고 Qdrant에 저장합니다
author: AI Agent
created: 2025-11-13
updated: 2025-11-13
dependencies:
    - app.vectorstore.vector_client (Qdrant 연동)
    - app.ai_pipeline.preprocess.embedding_pipeline (BGE-M3)
    - pathlib, json, logging

데이터 흐름:
1. /data/embeddings/*_chunks.json 읽기 (청크 정보)
2. 각 청크 임베딩 생성 (BGE-M3, 1024차원)
3. Qdrant에 저장 (메타데이터 포함)
4. 검색 테스트
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger(__name__)

# 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # /home/minje/remon
EMBEDDINGS_DIR = PROJECT_ROOT / "data" / "embeddings"

# sys.path 등록 (어디서 실행해도 'app' 모듈 임포트 가능하도록)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger.info(f"📁 프로젝트 루트: {PROJECT_ROOT}")
logger.info(f"📊 메타데이터 디렉토리: {EMBEDDINGS_DIR}")


class EmbeddingToVectorDB:
    """청크를 임베딩으로 변환해서 Qdrant VectorDB에 저장"""

    def __init__(self):
        """초기화 - VectorClient와 EmbeddingPipeline 로드"""
        try:
            # Qdrant 클라이언트 초기화
            from app.vectorstore.vector_client import VectorClient

            self.vc = VectorClient()
            
            # 연결 테스트
            try:
                info = self.vc.get_collection_info()
                logger.info(f"✅ Qdrant 연결 성공: {info}")
            except Exception as conn_e:
                logger.error(f"❌ Qdrant 서버 연결 실패: {conn_e}")
                logger.error("   해결방법:")
                logger.error("   1. bash scripts/start_qdrant.sh")
                logger.error("   2. docker ps | grep qdrant (실행 확인)")
                logger.error("   3. .env 파일에 QDRANT_USE_LOCAL=false 설정")
                raise
                
        except ImportError as e:
            logger.error(f"❌ Qdrant 라이브러리 미설치: {e}")
            logger.error("   해결방법: uv pip install qdrant-client")
            raise
        except Exception as e:
            logger.error(f"❌ Qdrant 초기화 실패: {e}")
            raise

        try:
            # 임베딩 파이프라인 초기화
            from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline

            self.embedder = EmbeddingPipeline(use_sparse=False)
            
            # 모델 로드 테스트
            test_embedding = self.embedder.embed_single_text("테스트")
            if test_embedding and "dense" in test_embedding:
                logger.info("✅ 임베딩 모델(BGE-M3) 로드 완료")
            else:
                raise RuntimeError("모델 초기화되었으나 임베딩 생성 실패")
                
        except ImportError as e:
            logger.error(f"❌ 임베딩 라이브러리 미설치: {e}")
            logger.error("   해결방법:")
            logger.error("   uv pip install sentence-transformers FlagEmbedding torch")
            raise
        except Exception as e:
            logger.error(f"❌ 임베딩 모델 로드 실패: {e}")
            logger.error("   가능한 원인:")
            logger.error("   1. GPU 메모리 부족")
            logger.error("   2. 모델 다운로드 실패")
            logger.error("   3. torch 버전 비호환")
            raise

        self.results = {
            "start_time": datetime.now().isoformat(),
            "total_chunks": 0,
            "saved_chunks": 0,
            "failed_chunks": 0,
            "files": [],
        }

    def run(self) -> Dict[str, Any]:
        """
        전체 프로세스 실행.

        단계:
        1. /data/embeddings에서 *_chunks.json 파일 수집
        2. 각 파일의 청크 읽기
        3. 청크 텍스트 임베딩 생성
        4. Qdrant에 저장 (메타데이터 포함)
        5. 결과 보고
        """
        logger.info("\n" + "=" * 70)
        logger.info("🚀 Step 2: 청크 임베딩 → Qdrant VectorDB 저장 시작")
        logger.info("=" * 70 + "\n")

        # 1단계: 청크 파일 수집 및 검증
        chunk_files = list(EMBEDDINGS_DIR.glob("*_chunks.json"))
        logger.info(f"📋 발견된 청크 파일: {len(chunk_files)}개\n")

        if not chunk_files:
            logger.error("❌ 청크 파일을 찾을 수 없습니다!")
            logger.error(f"   경로: {EMBEDDINGS_DIR}")
            logger.error("   해결방법:")
            logger.error("   1. cd /home/minje/remon")
            logger.error("   2. python app/ai_pipeline/preprocess/demo/test_preprocess_demo.py")
            logger.error("   3. 다시 이 스크립트 실행")
            return self.results
        
        # 파일 유효성 검증
        valid_files = []
        for f in chunk_files:
            try:
                with open(f, 'r') as test_f:
                    data = json.load(test_f)
                    if 'chunks' in data and len(data['chunks']) > 0:
                        valid_files.append(f)
                    else:
                        logger.warning(f"⚠️  빈 청크 파일 스킵: {f.name}")
            except Exception as e:
                logger.warning(f"⚠️  손상된 파일 스킵: {f.name} - {e}")
        
        chunk_files = valid_files
        logger.info(f"✅ 유효한 청크 파일: {len(chunk_files)}개")

        # 2단계: 각 파일 처리
        for file_idx, chunk_file in enumerate(chunk_files, 1):
            logger.info(
                f"\n[{file_idx}/{len(chunk_files)}] 📄 처리 중: {chunk_file.name}"
            )
            logger.info("-" * 70)

            try:
                file_result = self._process_chunk_file(chunk_file)
                self.results["files"].append(file_result)

            except Exception as e:
                logger.error(f"❌ 파일 처리 실패: {e}")
                self.results["files"].append(
                    {
                        "filename": chunk_file.name,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        # 3단계: 결과 저장 및 보고
        self.results["end_time"] = datetime.now().isoformat()
        self._print_summary()

        return self.results

    def _process_chunk_file(self, chunk_file: Path) -> Dict[str, Any]:
        """
        단일 청크 파일 처리.

        Args:
            chunk_file: *_chunks.json 파일 경로

        Returns:
            Dict: 처리 결과
        """
        file_result = {
            "filename": chunk_file.name,
            "status": "processing",
            "chunks_processed": 0,
            "chunks_saved": 0,
            "chunks_failed": 0,
        }

        try:
            # 청크 파일 읽기
            with open(chunk_file, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)

            chunks = chunk_data.get("chunks", [])
            num_chunks = len(chunks)
            logger.info(f"   📦 {num_chunks}개 청크 발견")

            if not chunks:
                logger.warning("   ⚠️  청크가 없습니다")
                file_result["status"] = "empty"
                file_result["reason"] = "no_chunks_found"
                return file_result
            
            # 청크 데이터 유효성 검증
            valid_chunks = []
            for chunk in chunks:
                if chunk.get("text") and len(chunk["text"].strip()) > 10:
                    valid_chunks.append(chunk)
                else:
                    logger.debug(f"   빈 청크 스킵: {chunk.get('chunk_id', 'unknown')}")
            
            if not valid_chunks:
                logger.warning("   ⚠️  유효한 청크가 없습니다")
                file_result["status"] = "empty"
                return file_result
            
            chunks = valid_chunks
            num_chunks = len(chunks)
            logger.info(f"   ✅ 유효한 청크: {num_chunks}개")

            # 각 청크 처리
            chunk_texts = []
            chunk_metadatas = []
            chunk_ids = []

            for chunk in chunks:
                chunk_id = chunk.get("chunk_id", "unknown")
                text = chunk.get("text", "")

                chunk_ids.append(chunk_id)
                chunk_texts.append(text)

                # 메타데이터 구성
                metadata = {
                    "chunk_id": chunk_id,
                    "section": chunk.get("section", ""),
                    "section_title": chunk.get("section_title", ""),
                    "subsection": chunk.get("subsection", ""),
                    "hierarchy_path": chunk.get("hierarchy_path", ""),
                    "hierarchy_depth": chunk.get("hierarchy_depth", 0),
                    "has_table": chunk.get("has_table", False),
                    "tokens_estimate": chunk.get("tokens_estimate", 0),
                    "source_file": chunk_file.stem,  # 파일명 (확장자 제외)
                }
                chunk_metadatas.append(metadata)

            # 임베딩 생성
            logger.info(f"   🧠 임베딩 생성 중... ({num_chunks}개)")
            embeddings_result = self.embedder.embed_texts(chunk_texts, normalize=True)
            embeddings = embeddings_result.get("dense", [])
            logger.info(f"   ✓ 임베딩 생성 완료")

            # Qdrant에 저장
            logger.info(f"   💾 Qdrant에 저장 중...")
            try:
                upserted_count = self.vc.upsert(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    metadatas=chunk_metadatas,
                    documents=chunk_texts,
                )
                logger.info(f"   ✓ {upserted_count}개 청크 저장 완료")
            except Exception as qdrant_e:
                logger.error(f"   ❌ Qdrant 저장 실패: {qdrant_e}")
                logger.error("   가능한 원인:")
                logger.error("   1. Qdrant 서버 연결 끊어짐")
                logger.error("   2. 메모리 부족")
                logger.error("   3. 데이터 형식 오류")
                raise qdrant_e

            # 결과 업데이트
            file_result["status"] = "success"
            file_result["chunks_processed"] = num_chunks
            file_result["chunks_saved"] = upserted_count
            file_result["chunks_failed"] = num_chunks - upserted_count

            self.results["total_chunks"] += num_chunks
            self.results["saved_chunks"] += upserted_count
            self.results["failed_chunks"] += num_chunks - upserted_count

        except Exception as e:
            logger.error(f"   ❌ 오류: {str(e)}")
            file_result["status"] = "failed"
            file_result["error"] = str(e)

        return file_result

    def _print_summary(self) -> None:
        """최종 요약 출력"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 Step 2 완료 요약")
        logger.info("=" * 70)
        logger.info(f"총 청크: {self.results['total_chunks']}개")
        logger.info(f"✅ 저장 완료: {self.results['saved_chunks']}개")
        logger.info(f"❌ 저장 실패: {self.results['failed_chunks']}개")
        logger.info(f"\n📍 Qdrant 위치:")
        logger.info(f"   - 서버: http://localhost:6333")
        logger.info(f"   - 대시보드: http://localhost:6333/dashboard")
        logger.info(f"   - 저장 경로: /data/qdrant (도커 볼륨)")
        logger.info(f"\n✨ 다음 단계:")
        logger.info(f"   1. Qdrant 대시보드에서 데이터 확인")
        logger.info(f"   2. python scripts/test_rag_query.py 실행")
        logger.info(f"   3. RAG 쿼리 테스트\n")


if __name__ == "__main__":
    try:
        runner = EmbeddingToVectorDB()
        results = runner.run()
    except Exception as e:
        logger.error(f"\n❌ 치명적 오류: {e}")
        sys.exit(1)
