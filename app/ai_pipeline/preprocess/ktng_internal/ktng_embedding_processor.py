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
    
    def __init__(self, collection_name: str = "remon_internal_ktng"):
        """
        초기화.
        
        Args:
            collection_name: VectorDB 컬렉션 이름
        """
        self.collection_name = collection_name
        
        # 기존 컴포넌트 재사용
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        from app.vectorstore.vector_client import VectorClient
        
        self.embedding_pipeline = EmbeddingPipeline(use_sparse=True)
        self.vector_client = VectorClient(collection_name=collection_name)
        
        logger.info(f"✅ KTNG 임베딩 프로세서 초기화: collection={collection_name}")
    
    async def process_and_store(self, combined_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                
                # 공통 메타데이터 추가
                metadata.update({
                    "meta_processed_at": datetime.utcnow().isoformat() + "Z",
                    "meta_embedding_model": "bge-m3",
                    "meta_collection": self.collection_name
                })
                
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
            
            # VectorDB에 저장
            self.vector_client.insert(
                texts=texts,
                dense_embeddings=dense_embeddings,
                metadatas=metadatas,
                sparse_embeddings=sparse_for_insert
            )
            
            # 5. 결과 반환
            result = {
                "status": "success",
                "collection_name": self.collection_name,
                "processed_chunks": len(combined_chunks),
                "embedding_dimension": len(dense_embeddings[0]) if dense_embeddings else 0,
                "has_sparse": sparse_embeddings is not None,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "summary": {
                    "total_texts": len(texts),
                    "total_embeddings": len(dense_embeddings),
                    "avg_text_length": sum(len(text) for text in texts) // len(texts),
                    "unique_products": len(set().union(*[
                        chunk["metadata"].get("meta_products", []) 
                        for chunk in combined_chunks
                    ])),
                    "unique_sections": len(set(
                        chunk["metadata"].get("meta_section", "") 
                        for chunk in combined_chunks
                    ))
                }
            }
            
            logger.info(f"✅ KTNG 임베딩 처리 완료: {len(combined_chunks)}개 청크 저장")
            return result
            
        except Exception as e:
            logger.error(f"❌ KTNG 임베딩 처리 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "processed_chunks": 0
            }
    
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회."""
        try:
            info = self.vector_client.get_collection_info()
            return {
                "collection_name": self.collection_name,
                "status": "exists",
                **info
            }
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
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
                filters={"meta_document_type": "internal_ktng_data"}
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
                        "section": meta.get("meta_section", "")
                    }
                    for doc, score, meta in zip(
                        results.get("documents", []),
                        results.get("scores", []),
                        results.get("metadatas", [])
                    )
                ]
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }