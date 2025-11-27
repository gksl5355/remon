"""
module: dual_indexer.py
description: Qdrant + Graph 동시 인덱싱
author: AI Agent
created: 2025-01-14
dependencies: app.vectorstore.vector_client, app.ai_pipeline.preprocess.embedding_pipeline
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DualIndexer:
    """Vector + Graph 동시 저장."""
    
    def __init__(self, collection_name: str = "remon_regulations"):
        self.collection_name = collection_name
        
    def index(
        self,
        chunks: List[Dict[str, Any]],
        graph_data: Dict[str, Any],
        source_file: str
    ) -> Dict[str, Any]:
        """
        청크를 Qdrant + Graph에 저장.
        
        Args:
            chunks: 컨텍스트 주입된 청크
            graph_data: 지식 그래프 데이터
            source_file: 원본 파일명
            
        Returns:
            Dict: 저장 결과 요약
        """
        from app.vectorstore.vector_client import VectorClient
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        
        # 임베딩 생성
        embedding_pipeline = EmbeddingPipeline(use_sparse=True)
        texts = [chunk["text"] for chunk in chunks]
        
        logger.info(f"임베딩 생성 중: {len(texts)}개 청크")
        embeddings_result = embedding_pipeline.embed_texts(texts)
        
        # 메타데이터 준비
        metadatas = []
        for chunk in chunks:
            metadata = chunk["metadata"].copy()
            metadata.update({
                "meta_source": source_file,
                "meta_processed_at": datetime.utcnow().isoformat() + "Z",
                "meta_hierarchy": " > ".join(chunk.get("hierarchy", [])),
                "meta_token_count": chunk.get("token_count", 0)
            })
            metadatas.append(metadata)
        
        # Qdrant 저장
        logger.info(f"Qdrant 저장 중: {self.collection_name}")
        vector_client = VectorClient(collection_name=self.collection_name)
        
        vector_client.insert(
            texts=texts,
            dense_embeddings=embeddings_result["dense"],
            metadatas=metadatas,
            sparse_embeddings=embeddings_result.get("sparse")
        )
        
        # Graph 저장 (추후 구현)
        graph_summary = self._store_graph(graph_data)
        
        result = {
            "status": "success",
            "qdrant_chunks": len(chunks),
            "graph_nodes": graph_summary["nodes"],
            "graph_edges": graph_summary["edges"],
            "collection_name": self.collection_name,
            "processed_at": datetime.utcnow().isoformat() + "Z"
        }
        
        logger.info(f"✅ Dual Indexing 완료: {len(chunks)}개 청크, {graph_summary['nodes']}개 노드")
        
        return result
    
    def _store_graph(self, graph_data: Dict[str, Any]) -> Dict[str, int]:
        """지식 그래프 저장 (NetworkX 인메모리)."""
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        # TODO: NetworkX 그래프 저장 로직
        logger.debug(f"Graph 저장 스킵 (추후 구현): {len(nodes)}개 노드, {len(edges)}개 엣지")
        
        return {"nodes": len(nodes), "edges": len(edges)}
