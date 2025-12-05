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
        청크를 Qdrant + Graph에 저장 (마크다운 청킹 + 표 별도 처리).
        
        Args:
            chunks: 컨텍스트 주입된 청크 (사용 안 함, vision_results 우선)
            graph_data: 지식 그래프 데이터
            source_file: 원본 파일명
            regulation_id: 규제 ID (예: "FDA-2025-001")
            vision_results: Vision 추출 결과 (markdown_content + tables)
            
        Returns:
            Dict: 저장 결과 요약
        """
        from app.vectorstore.vector_client import VectorClient
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        
        # 마크다운 청킹 + 표 별도 처리
        all_chunks = self._extract_chunks_from_vision(vision_results, regulation_id) if vision_results else []
        
        if not all_chunks:
            logger.warning("청킹 결과 없음, 빈 결과 반환")
            return {
                "status": "error",
                "error": "No chunks extracted",
                "qdrant_chunks": 0
            }
        
        logger.info(f"총 청크: {len(all_chunks)}개 (마크다운 청킹 + 표)")
        texts = [chunk["text"] for chunk in all_chunks]
        metadatas_base = [chunk["metadata"] for chunk in all_chunks]
        
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
        
        # reference_blocks 카운트 계산
        ref_blocks_count = 0
        if vision_results:
            for page_result in vision_results:
                ref_blocks = page_result.get("structure", {}).get("reference_blocks", [])
                ref_blocks_count += len(ref_blocks)
        
        result = {
            "status": "success",
            "qdrant_chunks": len(texts),
            "reference_blocks_count": ref_blocks_count,
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
    
    def _extract_chunks_from_vision(
        self, 
        vision_results: List[Dict[str, Any]], 
        regulation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Vision 결과에서 마크다운 청킹 + 표 별도 처리.
        
        전략:
        1. markdown_content를 HierarchyChunker로 청킹 (헤더 기반)
        2. tables 배열을 별도 청크로 추가
        3. ref_id는 청크 인덱스 기반 (의미적 집합)
        """
        from app.ai_pipeline.preprocess.semantic_processing import HierarchyChunker
        
        chunker = HierarchyChunker(max_tokens=1024)
        all_chunks = []
        chunk_counter = 0
        
        # 문서 메타데이터 추출 (첫 페이지)
        doc_metadata = {}
        if vision_results:
            first_page = vision_results[0]
            doc_metadata = first_page.get("structure", {}).get("metadata", {})
        
        for page_result in vision_results:
            page_num = page_result.get("page_num")
            structure = page_result.get("structure", {})
            markdown_content = structure.get("markdown_content", "")
            tables = structure.get("tables", [])
            
            # 1. 마크다운 헤더 기반 청킹
            if markdown_content:
                md_chunks = chunker.chunk_document(markdown_content, page_num)
                
                for md_chunk in md_chunks:
                    chunk_counter += 1
                    ref_id = f"{regulation_id}-Chunk{chunk_counter:04d}"
                    
                    # 계층 구조 추출
                    hierarchy = md_chunk.get("hierarchy", [])
                    section_label = " > ".join(hierarchy) if hierarchy else f"Page {page_num}"
                    
                    all_chunks.append({
                        "text": md_chunk["text"],
                        "metadata": {
                            "ref_id": ref_id,
                            "regulation_id": regulation_id,
                            "content_type": "text",
                            "page_num": page_num,
                            "hierarchy": hierarchy,
                            "token_count": md_chunk.get("token_count", 0),
                            # 확장 메타데이터
                            "document_id": doc_metadata.get("document_id"),
                            "jurisdiction_code": doc_metadata.get("jurisdiction_code"),
                            "authority": doc_metadata.get("authority"),
                            "title": doc_metadata.get("title"),
                            "citation_code": doc_metadata.get("citation_code"),
                            "language": doc_metadata.get("language"),
                            "publication_date": doc_metadata.get("publication_date"),
                            "effective_date": doc_metadata.get("effective_date"),
                            "source_url": doc_metadata.get("source_url"),
                            "retrieval_datetime": doc_metadata.get("retrieval_datetime"),
                            "original_format": doc_metadata.get("original_format"),
                            "file_path": doc_metadata.get("file_path"),
                            "raw_text_path": doc_metadata.get("raw_text_path"),
                            "section_label": section_label,
                            "page_range": doc_metadata.get("page_range"),
                            "keywords": doc_metadata.get("keywords", []),
                            # 하위 호환
                            "country": doc_metadata.get("country") or doc_metadata.get("jurisdiction_code"),
                            "regulation_type": doc_metadata.get("regulation_type") or doc_metadata.get("authority")
                        }
                    })
            
            # 2. 표 별도 청킹
            for table_idx, table in enumerate(tables):
                chunk_counter += 1
                ref_id = f"{regulation_id}-Table{chunk_counter:04d}"
                
                # 표를 검색 가능한 텍스트로 변환
                table_text = self._table_to_text(table)
                
                all_chunks.append({
                    "text": table_text,
                    "metadata": {
                        "ref_id": ref_id,
                        "regulation_id": regulation_id,
                        "content_type": "table",
                        "page_num": page_num,
                        "table_caption": table.get("caption", f"Table {table_idx + 1}"),
                        "table_headers": table.get("headers", []),
                        "table_row_count": len(table.get("rows", [])),
                        # 확장 메타데이터 (텍스트 청크와 동일하게)
                        "document_id": doc_metadata.get("document_id"),
                        "jurisdiction_code": doc_metadata.get("jurisdiction_code"),
                        "authority": doc_metadata.get("authority"),
                        "title": doc_metadata.get("title"),
                        "citation_code": doc_metadata.get("citation_code"),
                        "language": doc_metadata.get("language"),
                        "publication_date": doc_metadata.get("publication_date"),
                        "effective_date": doc_metadata.get("effective_date"),
                        "source_url": doc_metadata.get("source_url"),
                        "retrieval_datetime": doc_metadata.get("retrieval_datetime"),
                        "original_format": doc_metadata.get("original_format"),
                        "file_path": doc_metadata.get("file_path"),
                        "raw_text_path": doc_metadata.get("raw_text_path"),
                        "section_label": table.get("caption", f"Table {table_idx + 1}"),
                        "page_range": doc_metadata.get("page_range"),
                        "keywords": doc_metadata.get("keywords", []),
                        "country": doc_metadata.get("country") or doc_metadata.get("jurisdiction_code"),
                        "regulation_type": doc_metadata.get("regulation_type") or doc_metadata.get("authority")
                    }
                })
        
        logger.info(f"청킹 완료: {len(all_chunks)}개 (마크다운: {chunk_counter - len([c for c in all_chunks if c['metadata']['content_type'] == 'table'])}개, 표: {len([c for c in all_chunks if c['metadata']['content_type'] == 'table'])}개)")
        return all_chunks
    
    def _table_to_text(self, table: Dict[str, Any]) -> str:
        """표를 마크다운 형태로 변환 (LLM 입력 최적화)."""
        lines = []
        
        # 캡션
        if table.get("caption"):
            lines.append(f"**{table['caption']}**")
            lines.append("")
        
        # 헤더
        headers = table.get("headers", [])
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---" for _ in headers]) + "|")
        
        # 행
        for row in table.get("rows", []):
            cells = [str(cell) if cell else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
        
        return "\n".join(lines)
