"""
module: vision_orchestrator.py
description: Vision-Centric Preprocessing Pipeline 전체 조율
author: AI Agent
created: 2025-01-14
"""

import logging
from typing import Dict, Any, List
from pathlib import Path

from .config import PreprocessConfig
from .vision_ingestion import PDFRenderer, ComplexityAnalyzer, VisionRouter, StructureExtractor, DocumentAnalyzer
from .semantic_processing import HierarchyChunker, ContextInjector, DualIndexer
from .graph_builder import EntityExtractor, GraphManager

logger = logging.getLogger(__name__)


class VisionOrchestrator:
    """Vision 기반 전처리 파이프라인 조율자."""
    
    def __init__(self):
        vision_config = PreprocessConfig.get_vision_config()
        
        self.renderer = PDFRenderer(dpi=vision_config["dpi"])
        self.complexity_analyzer = ComplexityAnalyzer()
        self.document_analyzer = DocumentAnalyzer(
            api_key=vision_config["api_key"],
            model="gpt-4o-mini"
        )
        self.vision_router = VisionRouter(
            api_key=vision_config["api_key"],
            model_complex=vision_config["model_complex"],
            model_simple=vision_config["model_simple"],
            complexity_threshold=vision_config["complexity_threshold"],
            max_tokens=vision_config["max_tokens"],
            temperature=vision_config["temperature"]
        )
        self.structure_extractor = StructureExtractor()
        self.hierarchy_chunker = HierarchyChunker(max_tokens=1024)
        self.context_injector = ContextInjector()
        self.dual_indexer = DualIndexer()
        self.entity_extractor = EntityExtractor()
        self.graph_manager = GraphManager()
        
        self.enable_graph = vision_config["enable_graph"]
        self.analysis_pages = vision_config["analysis_pages"]
        
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        PDF 전체 처리 파이프라인.
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            Dict: {
                "status": "success",
                "vision_extraction_result": [...],
                "graph_data": {...},
                "dual_index_summary": {...}
            }
        """
        logger.info(f"=== Vision Pipeline 시작: {Path(pdf_path).name} ===")
        
        try:
            # Phase 1: Vision Ingestion
            vision_results = self._phase1_vision_ingestion(pdf_path)
            
            # Phase 2: Semantic Processing
            processing_results = self._phase2_semantic_processing(vision_results, pdf_path)
            
            # Phase 3: Graph Building (선택적)
            if self.enable_graph:
                graph_data = self._phase3_graph_building(vision_results)
            else:
                graph_data = {"nodes": [], "edges": []}
            
            # Phase 4: Dual Indexing
            index_summary = self._phase4_dual_indexing(
                processing_results["chunks"],
                graph_data,
                Path(pdf_path).name
            )
            
            result = {
                "status": "success",
                "vision_extraction_result": vision_results,
                "graph_data": graph_data,
                "dual_index_summary": index_summary
            }
            
            logger.info(f"✅ Vision Pipeline 완료: {len(vision_results)}개 페이지 처리")
            
            return result
            
        except Exception as e:
            logger.exception(f"❌ Vision Pipeline 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _phase1_vision_ingestion(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Phase 1: PDF → 이미지 → Vision LLM → 구조화."""
        logger.info("Phase 1: Vision Ingestion 시작")
        
        # 1. PDF 렌더링
        rendered_pages = self.renderer.render_pages(pdf_path)
        
        # 0. 문서 분석 (첫 페이지들로 전략 수립)
        if self.analysis_pages > 0 and len(rendered_pages) >= self.analysis_pages:
            first_images = [p["image_base64"] for p in rendered_pages[:self.analysis_pages]]
            doc_analysis = self.document_analyzer.analyze(first_images)
            logger.info(f"문서 분석: {doc_analysis.get('document_type')} - {doc_analysis.get('recommended_strategy')}")
        else:
            doc_analysis = None
        
        vision_results = []
        
        for page_data in rendered_pages:
            page_num = page_data["page_num"]
            
            # 2. 복잡도 분석
            complexity = self.complexity_analyzer.analyze_page(pdf_path, page_num)
            
            # 3. Vision 추출
            extraction = self.vision_router.route_and_extract(
                image_base64=page_data["image_base64"],
                page_num=page_num,
                complexity_score=complexity["complexity_score"],
                system_prompt=StructureExtractor.SYSTEM_PROMPT
            )
            
            # 4. 구조화
            structure = self.structure_extractor.extract(
                extraction["content"],
                page_num
            )
            
            vision_results.append({
                "page_num": page_num,
                "model_used": extraction["model_used"],
                "complexity_score": complexity["complexity_score"],
                "has_table": complexity["has_table"],
                "structure": structure.dict(),
                "tokens_used": extraction.get("tokens_used", 0)
            })
        
        logger.info(f"Phase 1 완료: {len(vision_results)}개 페이지")
        return vision_results
    
    def _phase2_semantic_processing(
        self,
        vision_results: List[Dict[str, Any]],
        pdf_path: str
    ) -> Dict[str, Any]:
        """Phase 2: 청킹 + 컨텍스트 주입."""
        logger.info("Phase 2: Semantic Processing 시작")
        
        all_chunks = []
        
        for page_result in vision_results:
            structure = page_result["structure"]
            markdown_content = structure["markdown_content"]
            page_num = page_result["page_num"]
            
            # 청킹
            chunks = self.hierarchy_chunker.chunk_document(markdown_content, page_num)
            all_chunks.extend(chunks)
        
        # 컨텍스트 주입
        enriched_chunks = self.context_injector.inject_context(all_chunks)
        
        logger.info(f"Phase 2 완료: {len(enriched_chunks)}개 청크")
        
        return {"chunks": enriched_chunks}
    
    def _phase3_graph_building(self, vision_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Phase 3: 지식 그래프 구축."""
        logger.info("Phase 3: Graph Building 시작")
        
        # PageStructure 객체 재구성
        from .vision_ingestion.structure_extractor import PageStructure
        
        page_structures = [
            PageStructure(**result["structure"])
            for result in vision_results
        ]
        
        # 엔티티 추출
        graph_data = self.entity_extractor.extract_from_pages(page_structures)
        
        # 그래프 구축
        self.graph_manager.build_graph(graph_data)
        
        logger.info(f"Phase 3 완료: {len(graph_data['nodes'])}개 노드")
        
        return graph_data
    
    def _phase4_dual_indexing(
        self,
        chunks: List[Dict[str, Any]],
        graph_data: Dict[str, Any],
        source_file: str
    ) -> Dict[str, Any]:
        """Phase 4: Qdrant + Graph 저장."""
        logger.info("Phase 4: Dual Indexing 시작")
        
        summary = self.dual_indexer.index(chunks, graph_data, source_file)
        
        logger.info(f"Phase 4 완료: {summary['qdrant_chunks']}개 청크 저장")
        
        return summary
