"""
module: preprocess_orchestrator.py
description: 전체 Preprocess 파이프라인 조율 (모든 모듈 통합)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger, app.ai_pipeline.preprocess.config
    - app.ai_pipeline.preprocess.[metadata_extractor, definition_extractor, ...]
    - typing, json, datetime
"""

from typing import List, Dict, Optional, Any
import logging
import json
from datetime import datetime
from pathlib import Path

from app.ai_pipeline.preprocess.config import PreprocessConfig
from app.ai_pipeline.preprocess.metadata_extractor import MetadataExtractor
from app.ai_pipeline.preprocess.definition_extractor import DefinitionExtractor
from app.ai_pipeline.preprocess.bm25_indexer import BM25Indexer
from app.ai_pipeline.preprocess.pdf_processor import PDFProcessor
from app.ai_pipeline.preprocess.table_detector import TableDetector
from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
from app.ai_pipeline.preprocess.semantic_chunker import SemanticChunker
from app.ai_pipeline.preprocess.hybrid_search import HybridSearch
from app.ai_pipeline.preprocess.hierarchy_extractor import HierarchyExtractor
from app.ai_pipeline.preprocess.proposition_extractor import PropositionExtractor

logger = logging.getLogger(__name__)


class PreprocessOrchestrator:
    """
    전체 Preprocess 파이프라인을 조율하는 오케스트레이터.
    
    파이프라인:
    1. PDF 로드 & 텍스트 추출 (PDFProcessor)
    2. 메타데이터 추출 (MetadataExtractor)
    3. 정의 & 계층 구조 추출 (DefinitionExtractor, HierarchyExtractor)
    4. 테이블 감지 (TableDetector)
    5. 의미 기반 청크 분할 (SemanticChunker)
    6. 임베딩 생성 (EmbeddingPipeline)
    7. BM25 인덱싱 (BM25Indexer)
    8. Chroma VectorDB에 저장할 형식 준비
    
    출력: ChromaDB 저장 데이터 스키마 (별도 index_manager로 저장)
    """
    
    def __init__(self, config: PreprocessConfig = None):
        """
        오케스트레이터 초기화.
        
        Args:
            config (PreprocessConfig): 설정 객체. None이면 기본값 사용
        """
        self.config = config or PreprocessConfig()
        
        # 모든 모듈 초기화
        self.metadata_extractor = MetadataExtractor()
        self.definition_extractor = DefinitionExtractor()
        self.bm25_indexer = BM25Indexer()
        self.pdf_processor = PDFProcessor()
        self.table_detector = TableDetector()
        self.embedding_pipeline = EmbeddingPipeline(
            model_name=self.config.EMBEDDING_MODEL,
            use_fp16=self.config.USE_FP16,
            batch_size=self.config.EMBEDDING_BATCH_SIZE,
        )
        self.semantic_chunker = SemanticChunker(
            chunk_size=self.config.MAX_CHUNK_SIZE,
        )
        self.hybrid_search = HybridSearch(
            embedding_pipeline=self.embedding_pipeline,
            bm25_indexer=self.bm25_indexer,
            alpha=self.config.HYBRID_ALPHA,
            table_boost=self.config.TABLE_BOOST,
            category_boost=self.config.CATEGORY_BOOST,
        )
        self.hierarchy_extractor = HierarchyExtractor()
        self.proposition_extractor = PropositionExtractor(
            api_key=self.config.OPENAI_API_KEY,
            model=self.config.OPENAI_MODEL_PROPOSITION,
            max_workers=3
        )
        
        # Parent-Child Hierarchy 저장소
        self.parent_chunks: Dict[str, str] = {}
        self.processed_hashes: set = set()
        
        logger.info("✅ PreprocessOrchestrator 초기화 완료")
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        PDF 파일 전체를 처리합니다.
        
        Args:
            pdf_path (str): PDF 파일 경로
        
        Returns:
            Dict[str, Any]: {
                "status": "success" | "error",
                "doc_id": "생성된 문서 ID",
                "pipeline_output": {
                    "raw_text": "원본 텍스트",
                    "metadata": {...},
                    "definitions": {...},
                    "hierarchy": {...},
                    "tables": {...},
                    "chunks": [...],
                    "embeddings": [...],  # numpy 배열은 list로 변환
                    "search_index": {...},  # BM25 인덱스 정보
                },
                "chroma_ready_data": [  # Chroma에 바로 저장 가능
                    {
                        "id": "chunk_id",
                        "text": "청크 텍스트",
                        "metadata": {...},
                        "embedding": [0.1, 0.2, ...],
                    },
                    ...
                ]
            }
        """
        logger.info(f"📄 PDF 처리 시작: {pdf_path}")
        
        try:
            # Step 1: PDF 로드
            pdf_result = self.pdf_processor.load_and_extract(pdf_path)
            if pdf_result["status"] != "success":
                raise RuntimeError(f"PDF 추출 실패: {pdf_result.get('error')}")
            
            raw_text = pdf_result.get("full_text", "")
            doc_id = self._generate_doc_id(pdf_path)
            
            # Step 2: 메타데이터 추출
            metadata = self.metadata_extractor.extract_metadata(raw_text, source_url=pdf_path)
            metadata["doc_id"] = doc_id
            
            # Step 3: 정의 추출
            definitions = self.definition_extractor.extract_definitions(raw_text)
            
            # Step 4: 계층 구조 추출
            hierarchy = self.hierarchy_extractor.extract_hierarchy(raw_text)
            
            # Step 5: 테이블 감지 및 컨텍스트 바인딩
            tables_result = self.table_detector.detect_tables_in_text(raw_text)
            if tables_result.get("tables"):
                enriched_tables = self.table_detector.bind_table_context(
                    raw_text, tables_result["tables"]
                )
                tables_result["tables"] = enriched_tables
            
            # Step 6: 의미 기반 청크 분할
            chunking_result = self.semantic_chunker.chunk_document(raw_text, metadata)
            chunks = chunking_result["chunks"]
            
            # Step 7: 명제 추출 (병렬 처리)
            logger.info(f"  명제 추출 중 ({len(chunks)}개 청크)...")
            all_propositions = self.proposition_extractor.extract_propositions_batch(
                [{"content": c["text"]} for c in chunks]
            )
            
            # Step 8: Parent-Child 관계 구성
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                self.parent_chunks[chunk_id] = chunk["text"]
            
            # Step 9: 임베딩 생성 (명제 단위)
            all_proposition_texts = []
            proposition_metadata = []
            
            for chunk_idx, (chunk, propositions) in enumerate(zip(chunks, all_propositions)):
                chunk_id = f"{doc_id}_chunk_{chunk_idx}"
                for prop_idx, proposition in enumerate(propositions):
                    all_proposition_texts.append(proposition)
                    proposition_metadata.append({
                        "chunk_id": f"{chunk_id}_prop_{prop_idx}",
                        "parent_chunk_id": chunk_id,
                        "chunk_index": chunk_idx,
                        "proposition_index": prop_idx,
                        "parent_content": chunk["text"][:500]
                    })
            
            embeddings_result = self.embedding_pipeline.embed_texts(all_proposition_texts)
            embeddings_array = embeddings_result["dense"]
            sparse_embeddings = embeddings_result.get("sparse")
            
            # Step 10: BM25 인덱싱
            bm25_result = self.bm25_indexer.build_index(raw_text, metadata)
            
            # Step 11: Qdrant 저장용 데이터 구성 (명제 단위)
            qdrant_ready_data = self._prepare_for_qdrant_with_propositions(
                chunks, all_propositions, embeddings_array, proposition_metadata, metadata, tables_result, sparse_embeddings
            )
            
            # 최종 결과
            result = {
                "status": "success",
                "doc_id": doc_id,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "pipeline_output": {
                    "raw_text": raw_text[:1000] + "..." if len(raw_text) > 1000 else raw_text,  # 샘플
                    "metadata": metadata,
                    "definitions": definitions,
                    "hierarchy": hierarchy,
                    "tables": tables_result,
                    "chunks": chunks[:3],
                    "propositions_sample": all_propositions[:3],
                    "embeddings_stats": {
                        "num_embeddings": len(embeddings_array),
                        "num_propositions": len(all_proposition_texts),
                        "embedding_dim": len(embeddings_array[0]) if embeddings_array and len(embeddings_array) > 0 else 1024,
                    },
                    "search_index": bm25_result,
                },
                "qdrant_ready_data": qdrant_ready_data,
                "summary": {
                    "num_chunks": len(chunks),
                    "num_propositions": len(all_proposition_texts),
                    "num_definitions": len(definitions.get("definitions", [])),
                    "num_tables": tables_result.get("num_tables", 0),
                    "total_text_chars": len(raw_text),
                }
            }
            
            # Qdrant에 이중 저장 (Docker + 로컬)
            try:
                from app.vectorstore.vector_client import VectorClient
                logger.info(f"  💾 Qdrant VectorDB에 이중 저장 중 (Docker + 로컬)...")
                
                # Docker VectorClient
                vc_docker = VectorClient(use_local=False)
                # 로컬 VectorClient  
                vc_local = VectorClient(use_local=True)
                
                # 데이터 추출
                texts = [d["text"] for d in qdrant_ready_data]
                embeddings = [d["embedding"] for d in qdrant_ready_data]
                metadatas = [d["metadata"] for d in qdrant_ready_data]
                
                # Sparse embedding 추출 (있으면)
                sparse_embeddings = None
                if qdrant_ready_data and "sparse_embedding" in qdrant_ready_data[0]["metadata"]:
                    sparse_embeddings = [d["metadata"].pop("sparse_embedding") for d in qdrant_ready_data]
                
                # Docker에 저장
                vc_docker.insert(
                    texts=texts,
                    dense_embeddings=embeddings,
                    metadatas=metadatas,
                    sparse_embeddings=sparse_embeddings
                )
                
                # 로컬에도 저장
                logger.info(f"  💾 로컬 VectorDB에도 저장 중...")
                vc_local.insert(
                    texts=texts,
                    dense_embeddings=embeddings,
                    metadatas=metadatas,
                    sparse_embeddings=sparse_embeddings
                )
                
                logger.info(f"  ✅ Qdrant 이중 저장 완료: {len(texts)}개 명제 (Docker + 로컬)")
                result["qdrant_status"] = "saved_dual"
                result["qdrant_count"] = len(texts)
                result["storage_locations"] = {
                    "docker": "http://localhost:6333",
                    "local": "/home/minje/remon/data/qdrant"
                }
                
            except Exception as e:
                logger.error(f"  ❌ Qdrant 이중 저장 실패: {e}")
                result["qdrant_status"] = "failed"
                result["qdrant_error"] = str(e)
            
            # 중복 방지
            self.processed_hashes.add(metadata.get("document_hash"))
            
            logger.info(f"✅ PDF 처리 완료: {len(chunks)}개 청크 생성, {len(all_proposition_texts)}개 명제 임베딩")
            return result
        
        except Exception as e:
            logger.error(f"❌ PDF 처리 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    def _prepare_for_qdrant_with_propositions(
        self,
        chunks: List[Dict[str, Any]],
        all_propositions: List[List[str]],
        embeddings_array,
        proposition_metadata: List[Dict[str, Any]],
        doc_metadata: Dict[str, Any],
        tables_result: Dict[str, Any],
        sparse_embeddings=None,
    ) -> List[Dict[str, Any]]:
        """Qdrant VectorDB에 저장할 형식으로 데이터를 준비 (명제 단위)."""
        chroma_data = []
        legal_hierarchy = doc_metadata.get("legal_hierarchy", {})
        
        embedding_idx = 0
        for chunk_idx, (chunk, propositions) in enumerate(zip(chunks, all_propositions)):
            for prop_idx, proposition in enumerate(propositions):
                prop_meta = proposition_metadata[embedding_idx]
                
                # Dense embedding
                dense_emb = embeddings_array[embedding_idx].tolist() if hasattr(embeddings_array[embedding_idx], 'tolist') else embeddings_array[embedding_idx]
                
                chroma_doc = {
                    "id": prop_meta["chunk_id"],
                    "text": proposition,
                    "embedding": dense_emb,
                    "metadata": {
                        # Sparse embedding (선택적)
                        "sparse_embedding": sparse_embeddings[embedding_idx] if sparse_embeddings else None,
                        "meta_doc_id": doc_metadata.get("doc_id"),
                        "meta_parent_chunk_id": prop_meta["parent_chunk_id"],
                        "meta_parent_content": prop_meta["parent_content"],
                        "meta_chunk_index": chunk_idx,
                        "meta_proposition_index": prop_idx,
                        "meta_title": doc_metadata.get("title"),
                        "meta_country": doc_metadata.get("country"),
                        "meta_jurisdiction": doc_metadata.get("jurisdiction"),
                        "meta_agency": doc_metadata.get("regulatory_body"),
                        "meta_law_type": doc_metadata.get("law_type"),
                        "meta_regulation_type": doc_metadata.get("regulation_type"),
                        "meta_date": doc_metadata.get("publication_date"),
                        "meta_external_id": doc_metadata.get("external_id"),
                        "meta_section": chunk.get("section"),
                        "meta_section_title": chunk.get("section_title"),
                        "meta_has_table": chunk.get("has_table", False),
                        "meta_cfr_citation": legal_hierarchy.get("full_citation") if legal_hierarchy else None,
                        "meta_regulation_hierarchy": legal_hierarchy.get("regulation_type") if legal_hierarchy else None,
                    },
                }
                
                # Sparse embedding 제거 (None이면)
                if chroma_doc["metadata"]["sparse_embedding"] is None:
                    del chroma_doc["metadata"]["sparse_embedding"]
                chroma_data.append(chroma_doc)
                embedding_idx += 1
        
        logger.debug(f"Qdrant 저장용 데이터 준비: {len(chroma_data)}개 명제")
        return chroma_data
    
    def _generate_doc_id(self, pdf_path: str) -> str:
        """PDF 경로로부터 문서 ID를 생성합니다."""
        path = Path(pdf_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"doc_{path.stem}_{timestamp}"
    
    def batch_process_pdfs(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """
        여러 PDF를 배치로 처리합니다.
        
        Args:
            pdf_paths (List[str]): PDF 파일 경로 리스트
        
        Returns:
            List[Dict[str, Any]]: 처리 결과 리스트
        """
        results = []
        for idx, pdf_path in enumerate(pdf_paths, start=1):
            logger.info(f"처리 중: {idx}/{len(pdf_paths)} - {pdf_path}")
            result = self.process_pdf(pdf_path)
            results.append(result)
        
        logger.info(f"✅ {len(results)}개 PDF 배치 처리 완료")
        return results
