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
    
    def __init__(self, collection_name: str = "skala-2.4.17-regulation"):
        self.collection_name = collection_name
        
    def index(
        self,
        chunks: List[Dict[str, Any]],
        graph_data: Dict[str, Any],
        source_file: str,
        regulation_id: str = None,
        vision_results: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        청크를 Qdrant + Graph에 저장 (Reference ID 포함).
        
        Args:
            chunks: 컨텍스트 주입된 청크
            graph_data: 지식 그래프 데이터
            source_file: 원본 파일명
            regulation_id: 규제 ID (예: "FDA-2025-001")
            vision_results: Vision 추출 결과 (reference_blocks 포함)
            
        Returns:
            Dict: 저장 결과 요약
        """
        from app.vectorstore.vector_client import VectorClient
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        
        # Reference Blocks 추출 (Vision 결과에서)
        ref_blocks = self._extract_reference_blocks(vision_results, regulation_id) if vision_results else []
        
        # Reference Block이 있으면 우선 사용, 없으면 기존 chunks 사용
        if ref_blocks:
            logger.info(f"Reference Blocks 사용: {len(ref_blocks)}개")
            texts = [rb["text"] for rb in ref_blocks]
            metadatas_base = [rb["metadata"] for rb in ref_blocks]
        else:
            logger.info(f"기존 chunks 사용: {len(chunks)}개")
            texts = [chunk["text"] for chunk in chunks]
            metadatas_base = [chunk["metadata"] for chunk in chunks]
        
        # 임베딩 생성
        embedding_pipeline = EmbeddingPipeline(use_sparse=True)
        logger.info(f"임베딩 생성 중: {len(texts)}개")
        embeddings_result = embedding_pipeline.embed_texts(texts)
        
        # 메타데이터 준비
        metadatas = []
        for i, base_meta in enumerate(metadatas_base):
            metadata = base_meta.copy()
            metadata.update({
                "meta_source": source_file,
                "meta_processed_at": datetime.utcnow().isoformat() + "Z"
            })
            metadatas.append(metadata)
        
        # Qdrant 저장 (로컬 + 원격)
        storage_locations = []
        
        # 로컬 저장
        logger.info(f"Qdrant 로컬 저장 중: {self.collection_name}")
        local_client = VectorClient(collection_name=self.collection_name, use_local=True)
        local_client.insert(
            texts=texts,
            dense_embeddings=embeddings_result["dense"],
            metadatas=metadatas,
            sparse_embeddings=embeddings_result.get("sparse")
        )
        logger.info("✅ 로컬 Qdrant 저장 완료")
        storage_locations.append("local")
        
        # 원격 저장 (작은 배치 크기로 타임아웃 방지)
        try:
            logger.info(f"Qdrant 원격 저장 중: {self.collection_name} (배치 크기: 10)")
            remote_client = VectorClient(collection_name=self.collection_name, use_local=False)
            remote_client.insert(
                texts=texts,
                dense_embeddings=embeddings_result["dense"],
                metadatas=metadatas,
                sparse_embeddings=embeddings_result.get("sparse"),
                batch_size=10  # 타임아웃 방지
            )
            logger.info("✅ 원격 Qdrant 저장 완료")
            storage_locations.append("remote")
        except Exception as e:
            logger.warning(f"⚠️ 원격 Qdrant 저장 실패 (로컬만 저장됨): {e}")
        
        # Graph 저장 (추후 구현)
        graph_summary = self._store_graph(graph_data)
        
        result = {
            "status": "success",
            "qdrant_chunks": len(texts),
            "reference_blocks_count": len(ref_blocks) if ref_blocks else 0,
            "graph_nodes": graph_summary["nodes"],
            "graph_edges": graph_summary["edges"],
            "collection_name": self.collection_name,
            "storage_locations": storage_locations,
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
    
    def _extract_reference_blocks(
        self, 
        vision_results: List[Dict[str, Any]], 
        regulation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Vision 결과에서 Reference Blocks 추출 및 ref_id 생성.
        
        ref_id 형식: {regulation_id}-{section_ref}-P{page_num}
        예시: "FDA-US-Required-Warnings-1114.5(a)(3)-P12"
        """
        ref_blocks = []
        
        # 메타데이터 추출 (첫 페이지)
        doc_metadata = {}
        if vision_results:
            first_page = vision_results[0]
            doc_metadata = first_page.get("structure", {}).get("metadata", {})
        
        for page_result in vision_results:
            page_num = page_result.get("page_num")
            structure = page_result.get("structure", {})
            
            # Vision LLM이 추출한 reference_blocks
            blocks = structure.get("reference_blocks", [])
            
            for block in blocks:
                section_ref = block.get("section_ref", "UNKNOWN")
                
                # ref_id 생성
                ref_id = f"{regulation_id}-{section_ref}-P{page_num}"
                
                ref_blocks.append({
                    "text": block.get("text", ""),
                    "metadata": {
                        "ref_id": ref_id,
                        "regulation_id": regulation_id,
                        "section_ref": section_ref,
                        "page_num": page_num,
                        "keywords": block.get("keywords", []),
                        "start_line": block.get("start_line"),
                        "end_line": block.get("end_line"),
                        # 문서 메타데이터 (모든 블록에 포함)
                        "title": doc_metadata.get("title"),
                        "country": doc_metadata.get("country"),
                        "regulation_type": doc_metadata.get("regulation_type"),
                        "effective_date": doc_metadata.get("effective_date")
                    }
                })
        
        logger.info(f"Reference Blocks 추출 완료: {len(ref_blocks)}개")
        return ref_blocks
