"""
module: ktng_embedding_processor.py
description: KTNG 임베딩 처리 및 별도 컬렉션 저장
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - app.ai_pipeline.preprocess.embedding_pipeline
    - app.vectorstore.vector_client
"""

from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KTNGEmbeddingProcessor:
    """KTNG 데이터 임베딩 처리 및 VectorDB 저장."""

    def __init__(
        self,
        collection_name: str = "remon_internal_ktng",
        reset_collection: bool = False,
    ):
        """
        초기화.

        Args:
            collection_name: VectorDB 컬렉션 이름
            reset_collection: True면 기존 컬렉션 삭제 후 새로 생성
        """
        self.collection_name = collection_name
        self.reset_collection = reset_collection

        # 기존 컴포넌트 재사용
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        from app.vectorstore.vector_client import VectorClient

        self.embedding_pipeline = EmbeddingPipeline(use_sparse=True)
        self.vector_client = VectorClient(collection_name=collection_name)

        # 이중 저장을 위한 로컬 클라이언트 추가
        self.local_client = VectorClient(
            collection_name=collection_name, use_local=True
        )

        # 처리된 파일 추적 (중복 방지)
        self.processed_files = set()

        # 컬렉션 초기화 (옵션)
        if reset_collection:
            try:
                self.vector_client.delete_collection()
                self.local_client.delete_collection()
                logger.info(f"✅ 기존 컬렉션 삭제: {collection_name}")

                # 새 컬렉션 생성
                self.vector_client._ensure_collection()
                self.local_client._ensure_collection()
                logger.info(f"✅ 새 컬렉션 생성: {collection_name}")
            except Exception as e:
                logger.warning(f"⚠️ 컬렉션 초기화 실패: {e}")

        logger.info(
            f"✅ KTNG 임베딩 프로세서 초기화: collection={collection_name} (이중 저장 모드, reset={reset_collection})"
        )

    async def process_and_store(
        self, combined_chunks: List[Dict[str, Any]], source_file: str = None
    ) -> Dict[str, Any]:
        """
        결합 청크를 임베딩하여 별도 컬렉션에 저장.

        Args:
            combined_chunks: RegulationProductChunking에서 생성한 결합 청크

        Returns:
            Dict: 처리 결과
        """
        logger.info(f"KTNG 임베딩 처리 시작: {len(combined_chunks)}개 청크")

        if not combined_chunks:
            return {"status": "error", "message": "처리할 청크가 없습니다"}

        # 같은 파일 중복 처리 방지
        if source_file:
            file_hash = self._get_file_hash(source_file)
            if file_hash in self.processed_files:
                logger.warning(f"파일 이미 처리됨: {source_file}")
                return {
                    "status": "skipped",
                    "message": f"파일이 이미 처리되었습니다: {source_file}",
                    "processed_chunks": 0,
                }
            self.processed_files.add(file_hash)

        try:
            # 1. 텍스트 추출
            texts = [chunk["text"] for chunk in combined_chunks]

            # 2. 임베딩 생성
            logger.info("  임베딩 생성 중...")
            embeddings_result = self.embedding_pipeline.embed_texts(texts)
            dense_embeddings = embeddings_result["dense"]
            sparse_embeddings = embeddings_result.get("sparse")

            # 3. 메타데이터 준비
            metadatas = []
            for i, chunk in enumerate(combined_chunks):
                metadata = chunk["metadata"].copy()

                # 처리 정보 추가 (기존 메타데이터 유지)
                metadata.update(
                    {
                        # 처리 정보
                        "meta_processed_at": datetime.utcnow().isoformat() + "Z",
                        "meta_embedding_model": "bge-m3",
                        "meta_collection": self.collection_name,
                        # 소스 파일 정보
                        "meta_source_file": (
                            source_file.split("/")[-1] if source_file else "json_cases"
                        ),
                    }
                )

                # Sparse 임베딩이 있으면 메타데이터에 추가
                if sparse_embeddings and i < len(sparse_embeddings):
                    metadata["sparse_embedding"] = sparse_embeddings[i]

                metadatas.append(metadata)

            # 4. VectorDB 저장
            logger.info(f"  VectorDB 저장 중: {self.collection_name}")

            # Sparse 임베딩 분리 (VectorClient.insert 형식에 맞춤)
            sparse_for_insert = None
            if sparse_embeddings:
                sparse_for_insert = []
                for metadata in metadatas:
                    sparse_emb = metadata.pop("sparse_embedding", None)
                    sparse_for_insert.append(sparse_emb)

            # Docker VectorDB에 저장
            self.vector_client.insert(
                texts=texts,
                dense_embeddings=dense_embeddings,
                metadatas=metadatas,
                sparse_embeddings=sparse_for_insert,
            )

            # 로컬 VectorDB에도 저장 (이중 저장)
            logger.info(f"  로컬 VectorDB 저장 중: {self.collection_name}")
            self.local_client.insert(
                texts=texts,
                dense_embeddings=dense_embeddings,
                metadatas=metadatas,
                sparse_embeddings=sparse_for_insert,
            )

            # 5. 결과 반환
            result = {
                "status": "success",
                "collection_name": self.collection_name,
                "storage_mode": "dual (Docker + Local)",
                "docker_path": "http://localhost:6333",
                "local_path": "/home/minje/remon/data/qdrant",
                "processed_chunks": len(combined_chunks),
                "embedding_dimension": (
                    len(dense_embeddings[0]) if dense_embeddings else 0
                ),
                "has_sparse": sparse_embeddings is not None,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "summary": {
                    "total_texts": len(texts),
                    "total_embeddings": len(dense_embeddings),
                    "avg_text_length": sum(len(text) for text in texts) // len(texts),
                    "unique_products": len(
                        set().union(
                            *[
                                chunk["metadata"].get("meta_products", [])
                                for chunk in combined_chunks
                            ]
                        )
                    ),
                    "unique_sections": len(
                        set(
                            chunk["metadata"].get("meta_section", "")
                            for chunk in combined_chunks
                        )
                    ),
                },
            }

            logger.info(
                f"✅ KTNG 임베딩 처리 완료: {len(combined_chunks)}개 청크 이중 저장 (Docker + 로컬)"
            )

            # 처리 완료된 파일 기록
            if source_file:
                result["processed_file"] = source_file
                result["file_hash"] = self._get_file_hash(source_file)
                result["reset_collection"] = self.reset_collection

            return result

        except Exception as e:
            logger.error(f"❌ KTNG 임베딩 처리 실패: {e}")
            return {"status": "error", "error": str(e), "processed_chunks": 0}

    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회."""
        try:
            info = self.vector_client.get_collection_info()
            return {"collection_name": self.collection_name, "status": "exists", **info}
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e),
            }

    def test_search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """테스트 검색 실행."""
        try:
            # 쿼리 임베딩
            query_emb = self.embedding_pipeline.embed_single_text(query)

            # 검색 실행
            results = self.vector_client.search(
                query_dense=query_emb["dense"],
                query_sparse=query_emb.get("sparse"),
                top_k=top_k,
                filters={"meta_document_type": "internal_ktng_data"},
            )

            return {
                "status": "success",
                "query": query,
                "results_count": len(results.get("documents", [])),
                "results": [
                    {
                        "text": doc[:100] + "..." if len(doc) > 100 else doc,
                        "score": score,
                        "products": meta.get("meta_products", []),
                        "section": meta.get("meta_section", ""),
                    }
                    for doc, score, meta in zip(
                        results.get("documents", []),
                        results.get("scores", []),
                        results.get("metadatas", []),
                    )
                ],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_file_hash(self, file_path: str) -> str:
        """파일 해시 생성 (중복 방지용)."""
        import hashlib
        from pathlib import Path

        try:
            path = Path(file_path)
            # 파일명 + 크기 + 수정시간으로 해시 생성
            file_info = f"{path.name}_{path.stat().st_size}_{path.stat().st_mtime}"
            return hashlib.md5(file_info.encode()).hexdigest()
        except Exception:
            # 파일 정보 접근 실패 시 파일명만 사용
            return hashlib.md5(file_path.encode()).hexdigest()

    def check_file_processed(self, source_file: str) -> bool:
        """파일이 이미 처리되었는지 확인."""
        if not source_file:
            return False
        file_hash = self._get_file_hash(source_file)
        return file_hash in self.processed_files
