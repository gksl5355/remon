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
from app.ai_pipeline.preprocess.pdf_processor import PDFProcessor
from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
from app.ai_pipeline.preprocess.semantic_chunker import SemanticChunker
from app.ai_pipeline.preprocess.proposition_extractor import PropositionExtractor
from app.ai_pipeline.preprocess.table_detector import TableDetector
from app.ai_pipeline.preprocess.hierarchy_extractor import HierarchyExtractor
from app.ai_pipeline.preprocess.definition_extractor import DefinitionExtractor
from app.ai_pipeline.preprocess.embedding_to_vectordb import EmbeddingToVectorDB

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
        
        # 전체 파이프라인 모듈 초기화
        self.metadata_extractor = MetadataExtractor()
        self.pdf_processor = PDFProcessor()
        self.table_detector = TableDetector()
        self.hierarchy_extractor = HierarchyExtractor()
        self.definition_extractor = DefinitionExtractor()
        self.semantic_chunker = SemanticChunker(
            chunk_size=self.config.MAX_CHUNK_SIZE,
        )
        self.proposition_extractor = PropositionExtractor(
            api_key=self.config.OPENAI_API_KEY,
            model=self.config.OPENAI_MODEL_PROPOSITION,
            max_workers=3
        )
        self.embedding_pipeline = EmbeddingPipeline(
            model_name=self.config.EMBEDDING_MODEL,
            use_fp16=self.config.USE_FP16,
            batch_size=self.config.EMBEDDING_BATCH_SIZE,
            use_sparse=True  # Sparse 벡터 활성화
        )
        self.embedding_to_vectordb = EmbeddingToVectorDB()
        
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
            
            # Step 3: 테이블 감지
            logger.info("  📊 테이블 감지 중...")
            table_results = self.table_detector.detect_and_convert_tables(raw_text)
            
            # Step 4: 계층 구조 추출
            logger.info("  🏗️ 계층 구조 추출 중...")
            hierarchy_results = self.hierarchy_extractor.extract_hierarchy(raw_text)
            
            # Step 5: 정의 추출
            logger.info("  📖 정의 추출 중...")
            definition_results = self.definition_extractor.extract_definitions_and_acronyms(raw_text)
            
            # Step 6: 의미 기반 청크 분할 (구조 정보 활용)
            # 구조 정보를 메타데이터에 추가
            enhanced_metadata = {
                **metadata,
                "tables": table_results,
                "hierarchy": hierarchy_results,
                "definitions": definition_results,
            }
            
            chunking_result = self.semantic_chunker.chunk_document(raw_text, enhanced_metadata)
            chunks = chunking_result["chunks"]
            
            # Step 7: 명제 추출 (병렬 처리) - 주석 처리
            # logger.info(f"  📝 명제 추출 중 ({len(chunks)}개 청크)...")
            # all_propositions = self.proposition_extractor.extract_propositions_batch(
            #     [{"content": c["text"]} for c in chunks]
            # )
            # 명제 추출 스킵 - 빈 리스트로 대체
            logger.info(f"  ⚠️ 명제 추출 스킵 (테스트용)")
            all_propositions = [[] for _ in chunks]  # 빈 명제 리스트
            
            # Step 8: Parent-Child 관계 구성
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                self.parent_chunks[chunk_id] = chunk["text"]
            
            # Step 9: 임베딩 생성 (원문 청크 단위, Dense + Sparse)
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings_result = self.embedding_pipeline.embed_texts(chunk_texts)
            embeddings_array = embeddings_result["dense"]
            sparse_embeddings = embeddings_result.get("sparse")  # Sparse 벡터 추출
            
            if sparse_embeddings:
                logger.info(f"  ✅ Sparse 벡터 생성 완료: {len(sparse_embeddings)}개")
            else:
                logger.warning("  ⚠️ Sparse 벡터 생성 실패 (FlagEmbedding 확인 필요)")
            
            # Step 10: VectorDB 저장용 데이터 구성 (원문 청크 단위)
            qdrant_ready_data = self._prepare_for_qdrant_with_chunks(
                chunks, all_propositions, embeddings_array, metadata, sparse_embeddings
            )
            
            # 최종 결과
            result = {
                "status": "success",
                "doc_id": doc_id,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "pipeline_output": {
                    "raw_text": raw_text[:1000] + "..." if len(raw_text) > 1000 else raw_text,  # 샘플
                    "metadata": metadata,
                    "tables": table_results,
                    "hierarchy": hierarchy_results,
                    "definitions": definition_results,
                    "chunks": chunks[:3],
                    "propositions_sample": all_propositions[:3],
                    "embeddings_stats": {
                        "num_embeddings": len(embeddings_array),
                        "num_chunks": len(chunks),
                        "embedding_dim": len(embeddings_array[0]) if embeddings_array and len(embeddings_array) > 0 else 1024,
                    },
                },
                "qdrant_ready_data": qdrant_ready_data,
                "summary": {
                    "num_chunks": len(chunks),
                    "num_propositions": sum(len(props) for props in all_propositions),
                    "total_text_chars": len(raw_text),
                }
            }
            
            # 텍스트 파일로 저장 (demo 폴더)
            try:
                output_dir = Path(__file__).parent / "demo"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                txt_file = output_dir / f"{doc_id}.txt"
                with open(txt_file, "w", encoding="utf-8") as f:
                    f.write("=" * 80 + "\n")
                    f.write("문서 메타데이터\n")
                    f.write("=" * 80 + "\n")
                    f.write(f"제목: {metadata['title']}\n")
                    f.write(f"국가: {metadata['country']}\n")
                    f.write(f"관할권: {metadata['jurisdiction']}\n")
                    f.write(f"규제기관: {metadata.get('regulatory_body', 'N/A')}\n")
                    f.write(f"법률 유형: {metadata.get('law_type', 'N/A')}\n")
                    f.write(f"발표일: {metadata.get('publication_date', 'N/A')}\n")
                    f.write(f"총 청크: {len(chunks)}개\n")
                    f.write(f"총 문자: {len(raw_text):,}개\n")
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("원문 텍스트\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(raw_text)
                    f.write("\n\n" + "=" * 80 + "\n")
                    f.write(f"청크 목록 ({len(chunks)}개)\n")
                    f.write("=" * 80 + "\n")
                    for i, chunk in enumerate(chunks, 1):
                        f.write(f"\n--- 청크 {i}/{len(chunks)} ---\n")
                        f.write(f"섹션: {chunk.get('section', 'N/A')}\n")
                        f.write(f"계층: {chunk.get('hierarchy_path', 'N/A')}\n")
                        f.write(f"테이블 포함: {chunk.get('has_table', False)}\n")
                        f.write(f"토큰 예상: {chunk.get('tokens_estimate', 0)}\n")
                        f.write(f"\n{chunk['text']}\n")
                
                logger.info(f"  💾 텍스트 파일 저장: {txt_file.name}")
                result["txt_file"] = str(txt_file)
                
            except Exception as e:
                logger.warning(f"  ⚠️ 텍스트 파일 저장 실패: {e}")
            
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
                
                logger.info(f"  ✅ Qdrant 이중 저장 완료: {len(texts)}개 청크 (Docker + 로컬)")
                result["qdrant_status"] = "saved_dual"
                result["qdrant_count"] = len(texts)
                result["storage_locations"] = {
                    "docker": "http://localhost:6333",
                    "local": "/home/minje/remon/data/qdrant",
                    "txt_file": result.get("txt_file", "N/A")
                }
                
            except Exception as e:
                logger.error(f"  ❌ Qdrant 이중 저장 실패: {e}")
                result["qdrant_status"] = "failed"
                result["qdrant_error"] = str(e)
            
            # 중복 방지
            self.processed_hashes.add(metadata.get("document_hash"))
            
            logger.info(f"✅ PDF 처리 완료: {len(chunks)}개 청크 생성 및 임베딩")
            return result
        
        except Exception as e:
            logger.error(f"❌ PDF 처리 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    def _prepare_for_qdrant_with_chunks(
        self,
        chunks: List[Dict[str, Any]],
        all_propositions: List[List[str]],
        embeddings_array,
        doc_metadata: Dict[str, Any],
        sparse_embeddings=None,
    ) -> List[Dict[str, Any]]:
        """Qdrant VectorDB에 저장할 형식으로 데이터를 준비 (원문 청크 단위, Dense + Sparse)."""
        chroma_data = []
        legal_hierarchy = doc_metadata.get("legal_hierarchy", {})
        sparse_count = 0
        
        for chunk_idx, (chunk, propositions) in enumerate(zip(chunks, all_propositions)):
            chunk_id = f"{doc_metadata.get('doc_id', 'unknown')}_chunk_{chunk_idx}"
            
            # Dense embedding
            dense_emb = embeddings_array[chunk_idx].tolist() if hasattr(embeddings_array[chunk_idx], 'tolist') else embeddings_array[chunk_idx]
            
            # Sparse embedding (있으면)
            sparse_emb = None
            if sparse_embeddings and chunk_idx < len(sparse_embeddings):
                sparse_emb = sparse_embeddings[chunk_idx]
                sparse_count += 1
            
            chroma_doc = {
                "id": chunk_id,
                "text": chunk["text"],  # 원문 청크 저장
                "embedding": dense_emb,
                "metadata": {
                    # Sparse embedding (있으면 포함)
                    "sparse_embedding": sparse_emb,
                    "meta_doc_id": doc_metadata.get("doc_id"),
                    "meta_chunk_index": chunk_idx,
                    "meta_propositions": propositions,  # 명제는 메타데이터로 저장
                    "meta_num_propositions": len(propositions),
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
        
        logger.debug(f"Qdrant 저장용 데이터 준비: {len(chroma_data)}개 청크 (중 Sparse: {sparse_count}개)")
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
    
    def process_regulatory_document_ddh(
        self,
        document_text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        DDH 표준 규제 문서를 Parent-Child 청킹으로 처리.
        
        Args:
            document_text: 규제 문서 텍스트
            document_metadata: 문서 메타데이터
            
        Returns:
            Dict: 처리 결과 (Parent-Child 청크 + Qdrant 준비 데이터)
        """
        logger.info("🏦 DDH 규제 문서 처리 시작 (Parent-Child 청킹)")
        
        try:
            if not document_metadata:
                document_metadata = {}
                
            doc_id = document_metadata.get("doc_id", self._generate_doc_id("ddh_document"))
            
            # Step 1: DDH 구조 파싱
            logger.info("  🏦 DDH 구조 파싱 중...")
            hierarchy_extractor_ddh = HierarchyExtractor(use_ddh=True)
            legal_nodes = hierarchy_extractor_ddh.parse_ddh_structure(document_text)
            preamble_metadata = hierarchy_extractor_ddh.get_preamble_metadata()
            
            # Step 2: 기술 용어 정규화
            logger.info("  📝 기술 용어 정규화 중...")
            definition_extractor_enhanced = DefinitionExtractor(use_domain_dict=True)
            
            # Step 3: Parent-Child 청킹
            logger.info("  ✂️ Parent-Child 청킹 중...")
            global_metadata = {
                **document_metadata,
                **preamble_metadata,
                "doc_id": doc_id,
                "processing_type": "ddh_parent_child",
                "processed_at": datetime.utcnow().isoformat() + "Z"
            }
            
            processed_chunks = self.semantic_chunker.create_parent_child_chunks(
                legal_nodes, global_metadata
            )
            
            # Step 4: 용어 정규화 적용
            for chunk in processed_chunks:
                chunk.text = definition_extractor_enhanced.normalize_tobacco_terms(chunk.text)
                chunk.context_text = definition_extractor_enhanced.normalize_tobacco_terms(chunk.context_text)
            
            # Step 5: 임베딩 생성 (Child + Parent 별도, Dense + Sparse)
            logger.info(f"  🧮 임베딩 생성 중 ({len(processed_chunks)}개 청크)...")
            
            child_texts = [chunk.text for chunk in processed_chunks if chunk.chunk_type == "child"]
            parent_texts = [chunk.text for chunk in processed_chunks if chunk.chunk_type == "parent"]
            
            # Child 임베딩 (Dense + Sparse)
            child_embeddings_result = self.embedding_pipeline.embed_texts(child_texts) if child_texts else {"dense": [], "sparse": []}
            if child_texts and child_embeddings_result.get("sparse"):
                logger.info(f"  ✅ Child Sparse 벡터: {len(child_embeddings_result['sparse'])}개")
            
            # Parent 임베딩 (Dense + Sparse)
            parent_embeddings_result = self.embedding_pipeline.embed_texts(parent_texts) if parent_texts else {"dense": [], "sparse": []}
            if parent_texts and parent_embeddings_result.get("sparse"):
                logger.info(f"  ✅ Parent Sparse 벡터: {len(parent_embeddings_result['sparse'])}개")
            
            # 임베딩을 청크에 할당 (Dense + Sparse)
            child_idx = 0
            parent_idx = 0
            
            for chunk in processed_chunks:
                if chunk.chunk_type == "child":
                    # Dense 임베딩
                    chunk.embedding = child_embeddings_result["dense"][child_idx].tolist() if hasattr(child_embeddings_result["dense"][child_idx], 'tolist') else child_embeddings_result["dense"][child_idx]
                    # Sparse 임베딩 (있으면)
                    if child_embeddings_result.get("sparse"):
                        chunk.sparse_embedding = child_embeddings_result["sparse"][child_idx]
                    child_idx += 1
                elif chunk.chunk_type == "parent":
                    # Dense 임베딩
                    chunk.parent_embedding = parent_embeddings_result["dense"][parent_idx].tolist() if hasattr(parent_embeddings_result["dense"][parent_idx], 'tolist') else parent_embeddings_result["dense"][parent_idx]
                    # Sparse 임베딩 (있으면)
                    if parent_embeddings_result.get("sparse"):
                        chunk.parent_sparse_embedding = parent_embeddings_result["sparse"][parent_idx]
                    parent_idx += 1
            
            # Step 6: Qdrant 저장용 데이터 준비
            qdrant_ready_data = self._prepare_parent_child_for_qdrant(
                processed_chunks, global_metadata
            )
            
            # Step 7: Qdrant에 저장
            try:
                from app.vectorstore.vector_client import VectorClient
                logger.info("  💾 Qdrant에 Parent-Child 저장 중...")
                
                vc = VectorClient()
                
                # 데이터 추출
                texts = [d["text"] for d in qdrant_ready_data]
                embeddings = [d["embedding"] for d in qdrant_ready_data]
                metadatas = [d["metadata"] for d in qdrant_ready_data]
                
                # Sparse embedding 추출 (있으면)
                sparse_embeddings = None
                if qdrant_ready_data and "sparse_embedding" in qdrant_ready_data[0]["metadata"]:
                    sparse_embeddings = [d["metadata"].pop("sparse_embedding") for d in qdrant_ready_data]
                
                vc.insert(
                    texts=texts,
                    dense_embeddings=embeddings,
                    metadatas=metadatas,
                    sparse_embeddings=sparse_embeddings
                )
                
                logger.info(f"  ✅ Qdrant 저장 완료: {len(texts)}개 청크")
                
            except Exception as e:
                logger.error(f"  ❌ Qdrant 저장 실패: {e}")
            
            # 결과 반환
            result = {
                "status": "success",
                "doc_id": doc_id,
                "processing_type": "ddh_parent_child",
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "ddh_parsing": {
                    "legal_nodes": len(legal_nodes),
                    "preamble_metadata": preamble_metadata,
                    "sections_parsed": [node.get("identifier") for node in legal_nodes]
                },
                "parent_child_chunking": {
                    "total_chunks": len(processed_chunks),
                    "parent_chunks": len([c for c in processed_chunks if c.chunk_type == "parent"]),
                    "child_chunks": len([c for c in processed_chunks if c.chunk_type == "child"])
                },
                "embeddings": {
                    "child_embeddings": len(child_texts),
                    "parent_embeddings": len(parent_texts),
                    "embedding_dim": len(processed_chunks[0].embedding) if processed_chunks and processed_chunks[0].embedding else 1024
                },
                "qdrant_ready_data": qdrant_ready_data,
                "summary": {
                    "sections": len(legal_nodes),
                    "total_chunks": len(processed_chunks),
                    "normalized_terms": len(definition_extractor_enhanced.get_all_terms())
                }
            }
            
            logger.info(f"✅ DDH 처리 완료: {len(legal_nodes)}개 섹션 → {len(processed_chunks)}개 Parent-Child 청크")
            return result
            
        except Exception as e:
            logger.error(f"❌ DDH 처리 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "processing_type": "ddh_parent_child"
            }
    
    def _prepare_parent_child_for_qdrant(
        self,
        processed_chunks: List,  # ProcessedChunk 리스트
        global_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parent-Child 청크를 Qdrant 저장 형식으로 변환 (Dense + Sparse).
        
        Args:
            processed_chunks: ProcessedChunk 리스트
            global_metadata: 전역 메타데이터
            
        Returns:
            List[Dict]: Qdrant 저장용 데이터
        """
        qdrant_data = []
        sparse_count = 0
        
        for chunk in processed_chunks:
            # Dense 임베딩 선택 (Child는 검색용, Parent는 맥락용)
            embedding = chunk.embedding if chunk.chunk_type == "child" else chunk.parent_embedding
            
            if not embedding:
                logger.warning(f"임베딩 누락: {chunk.chunk_id}")
                continue
            
            # Sparse 임베딩 선택
            sparse_embedding = chunk.sparse_embedding if chunk.chunk_type == "child" else chunk.parent_sparse_embedding
            if sparse_embedding:
                sparse_count += 1
                
            qdrant_doc = {
                "id": chunk.chunk_id,
                "text": chunk.text,
                "embedding": embedding,
                "metadata": {
                    # Sparse 임베딩 (있으면 메타데이터에 포함)
                    "sparse_embedding": sparse_embedding,
                    
                    # Parent-Child 관계
                    "type": chunk.chunk_type,
                    "parent_id": chunk.parent_id,
                    "context_text": chunk.context_text[:500] + "..." if len(chunk.context_text) > 500 else chunk.context_text,
                    
                    # 기본 메타데이터
                    "meta_doc_id": global_metadata.get("doc_id"),
                    "meta_section_id": chunk.metadata.get("section_id"),
                    "meta_hierarchy_level": chunk.metadata.get("hierarchy_level"),
                    "meta_level": chunk.metadata.get("level"),
                    "meta_is_table": chunk.metadata.get("is_table", False),
                    
                    # DDH 메타데이터
                    "meta_agency": global_metadata.get("AGENCY"),
                    "meta_action": global_metadata.get("ACTION"),
                    "meta_summary": global_metadata.get("SUMMARY", "")[:200],
                    "meta_country": global_metadata.get("country", "US"),
                    "meta_jurisdiction": global_metadata.get("jurisdiction", "federal"),
                    "meta_processing_type": global_metadata.get("processing_type"),
                    "meta_processed_at": global_metadata.get("processed_at")
                }
            }
            
            qdrant_data.append(qdrant_doc)
            
        logger.debug(f"Qdrant Parent-Child 데이터 준비: {len(qdrant_data)}개 (중 Sparse: {sparse_count}개)")
        return qdrant_data
