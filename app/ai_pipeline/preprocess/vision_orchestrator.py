"""
module: vision_orchestrator.py
description: Vision-Centric Preprocessing Pipeline 전체 조율 (병렬 처리 지원)
author: AI Agent
created: 2025-01-14
updated: 2025-01-14 (병렬 처리 리팩터링)
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field

from .config import PreprocessConfig
from .vision_ingestion import PDFRenderer, ComplexityAnalyzer, VisionRouter, StructureExtractor, DocumentAnalyzer
from .semantic_processing import HierarchyChunker, ContextInjector, DualIndexer
from .graph_builder import EntityExtractor, GraphManager

logger = logging.getLogger(__name__)


@dataclass
class TokenTracker:
    """토큰 사용량 추적."""
    total_tokens: int = 0
    tokens_by_model: Dict[str, int] = field(default_factory=dict)
    tokens_by_page: Dict[int, int] = field(default_factory=dict)
    
    def add_usage(self, page_num: int, model: str, tokens: int) -> None:
        """토큰 사용량 추가."""
        self.total_tokens += tokens
        self.tokens_by_model[model] = self.tokens_by_model.get(model, 0) + tokens
        self.tokens_by_page[page_num] = tokens
    
    def check_budget(self, budget: Optional[int]) -> bool:
        """예산 초과 여부 확인."""
        if budget is None:
            return True
        return self.total_tokens <= budget
    
    def get_summary(self) -> Dict[str, Any]:
        """사용량 요약 반환."""
        return {
            "total_tokens": self.total_tokens,
            "tokens_by_model": self.tokens_by_model.copy(),
            "page_count": len(self.tokens_by_page),
        }


class VisionOrchestrator:
    """Vision 기반 전처리 파이프라인 조율자 (병렬 처리 지원)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_complex: Optional[str] = None,
        model_simple: Optional[str] = None,
        dpi: Optional[int] = None,
        complexity_threshold: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_graph: Optional[bool] = None,
        analysis_pages: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        token_budget: Optional[int] = None,
        request_timeout: Optional[int] = None,
        retry_max_attempts: Optional[int] = None,
        retry_backoff_seconds: Optional[float] = None,
    ):
        """
        VisionOrchestrator 초기화.
        
        Args:
            api_key: OpenAI API 키 (필수)
            model_complex: 복잡한 표 처리용 모델 (기본값: gpt-4o)
            model_simple: 단순 텍스트 처리용 모델 (기본값: gpt-4o-mini)
            dpi: PDF 이미지 렌더링 DPI (기본값: 300)
            complexity_threshold: 표 복잡도 임계값 (기본값: 0.3)
            max_tokens: Vision LLM 최대 출력 토큰 (기본값: 4096)
            temperature: Vision LLM 온도 (기본값: 0.1)
            enable_graph: 지식 그래프 추출 활성화 (기본값: True)
            analysis_pages: 문서 규칙 파악용 초기 분석 페이지 수 (기본값: 3)
            max_concurrency: 페이지별 Vision LLM 호출 최대 동시 실행 수 (기본값: 3)
            token_budget: 문서 단위 토큰 예산 (기본값: None, 제한 없음)
            request_timeout: Vision API 요청 타임아웃 초 (기본값: 120)
            retry_max_attempts: Vision API 실패 시 최대 재시도 횟수 (기본값: 2)
            retry_backoff_seconds: 재시도 간 대기 시간 초 (기본값: 1.0)
        
        Note:
            인자가 None이면 PreprocessConfig에서 기본값을 가져옵니다.
        """
        # 기본값 로드 (인자가 None인 경우)
        vision_config = PreprocessConfig.get_vision_config()
        
        # 인자로 넘어온 값이 있으면 우선 사용, 없으면 config 기본값 사용
        self.api_key = api_key or vision_config["api_key"]
        model_complex = model_complex or vision_config["model_complex"]
        model_simple = model_simple or vision_config["model_simple"]
        dpi = dpi or vision_config["dpi"]
        complexity_threshold = complexity_threshold or vision_config["complexity_threshold"]
        max_tokens = max_tokens or vision_config["max_tokens"]
        temperature = temperature or vision_config["temperature"]
        request_timeout = request_timeout or vision_config["request_timeout"]
        retry_max_attempts = retry_max_attempts or vision_config["retry_max_attempts"]
        retry_backoff_seconds = retry_backoff_seconds or vision_config["retry_backoff_seconds"]
        self.enable_graph = enable_graph if enable_graph is not None else vision_config["enable_graph"]
        self.analysis_pages = analysis_pages or vision_config["analysis_pages"]
        self.max_concurrency = max_concurrency or vision_config["max_concurrency"]
        self.token_budget = token_budget if token_budget is not None else vision_config["token_budget"]
        
        if not self.api_key:
            raise ValueError("api_key는 필수입니다. 생성자 인자로 전달하거나 환경 변수 OPENAI_API_KEY를 설정하세요.")
        
        self.renderer = PDFRenderer(dpi=dpi)
        self.complexity_analyzer = ComplexityAnalyzer()
        self.document_analyzer = DocumentAnalyzer(
            api_key=self.api_key,
            model="gpt-4o-mini"
        )
        self.vision_router = VisionRouter(
            api_key=self.api_key,
            model_complex=model_complex,
            model_simple=model_simple,
            complexity_threshold=complexity_threshold,
            max_tokens=max_tokens,
            temperature=temperature,
            request_timeout=request_timeout,
            retry_max_attempts=retry_max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self.structure_extractor = StructureExtractor()
        self.hierarchy_chunker = HierarchyChunker(max_tokens=1024)
        self.context_injector = ContextInjector()
        self.dual_indexer = DualIndexer()
        self.entity_extractor = EntityExtractor()
        self.graph_manager = GraphManager()
        
    def process_pdf(self, pdf_path: str, use_parallel: bool = True) -> Dict[str, Any]:
        """
        PDF 전체 처리 파이프라인.
        
        Args:
            pdf_path: PDF 파일 경로
            use_parallel: 병렬 처리 사용 여부 (기본값: True)
            
        Returns:
            Dict: {
                "status": "success",
                "vision_extraction_result": [...],
                "graph_data": {...},
                "dual_index_summary": {...}
            }
        """
        logger.info(f"=== Vision Pipeline 시작: {Path(pdf_path).name} (병렬: {use_parallel}) ===")
        
        try:
            # Phase 1: Vision Ingestion
            if use_parallel and self.max_concurrency > 1:
                # 비동기 병렬 처리
                vision_results = asyncio.run(self._phase1_vision_ingestion_parallel(pdf_path))
            else:
                # 순차 처리 (기존 방식)
                vision_results = self._phase1_vision_ingestion(pdf_path)
            
            if not vision_results:
                logger.warning("처리된 페이지가 없습니다.")
                return {
                    "status": "error",
                    "error": "No pages processed"
                }
            
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
                "dual_index_summary": index_summary,
                "processing_results": processing_results  # 테스트용으로 추가
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
        """
        Phase 1: PDF → 이미지 → Vision LLM → 구조화 (동기, 동적 DPI).
        
        병렬 처리를 원하면 _phase1_vision_ingestion_parallel() 사용.
        """
        logger.info("Phase 1: Vision Ingestion 시작 (순차 처리, 동적 DPI)")
        
        # PDF 페이지 수 확인
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        pdf.close()
        
        vision_results = []
        token_tracker = TokenTracker()
        
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            
            try:
                # 1. 복잡도 분석
                complexity = self.complexity_analyzer.analyze_page(pdf_path, page_num)
                
                # 2. DPI 결정 (복잡도 기반)
                if complexity["has_table"] or complexity["complexity_score"] >= 0.3:
                    dpi = 300  # 표 있음 → 고해상도
                    logger.info(f"페이지 {page_num}: 복잡도 {complexity['complexity_score']:.2f} → 300 DPI")
                else:
                    dpi = 150  # 단순 텍스트 → 저해상도
                    logger.info(f"페이지 {page_num}: 복잡도 {complexity['complexity_score']:.2f} → 150 DPI")
                
                # 3. 동적 렌더링
                page_data = self.renderer.render_page_with_dpi(pdf_path, page_idx, dpi)
                
                # 4. Vision 추출
                extraction = self.vision_router.route_and_extract(
                    image_base64=page_data["image_base64"],
                    page_num=page_num,
                    complexity_score=complexity["complexity_score"],
                    system_prompt=StructureExtractor.SYSTEM_PROMPT
                )
                
                # 토큰 사용량 추적
                tokens_used = extraction.get("tokens_used", 0)
                token_tracker.add_usage(page_num, extraction["model_used"], tokens_used)
                
                # 예산 확인
                if not token_tracker.check_budget(self.token_budget):
                    logger.warning(
                        f"토큰 예산 초과: {token_tracker.total_tokens}/{self.token_budget}. "
                        f"페이지 {page_num}부터 처리 중단."
                    )
                    break
                
                # 5. 구조화
                structure = self.structure_extractor.extract(
                    extraction["content"],
                    page_num
                )
                
                vision_results.append({
                    "page_num": page_num,
                    "model_used": extraction["model_used"],
                    "complexity_score": complexity["complexity_score"],
                    "has_table": complexity["has_table"],
                    "dpi": dpi,  # DPI 기록
                    "structure": structure.dict(),
                    "tokens_used": tokens_used
                })
                
                logger.debug(f"페이지 {page_num} 완료: {dpi} DPI, {tokens_used} 토큰")
                
            except Exception as e:
                logger.error(f"페이지 {page_num} 실패: {e}", exc_info=True)
                continue
        
        logger.info(
            f"Phase 1 완료: {len(vision_results)}/{total_pages}개 페이지. "
            f"총 토큰: {token_tracker.total_tokens}"
        )
        return vision_results
    
    async def _phase1_vision_ingestion_parallel(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Phase 1: PDF → 이미지 → Vision LLM → 구조화 (병렬 처리, 동적 DPI).
        
        페이지별 Vision LLM 호출을 병렬로 처리하여 처리 시간 단축.
        """
        logger.info(f"Phase 1: Vision Ingestion 시작 (병렬 처리, 동적 DPI, max_concurrency={self.max_concurrency})")
        
        # PDF 페이지 수 확인
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        pdf.close()
        
        # 1. 복잡도 분석 및 DPI 결정 (모든 페이지)
        complexity_results = {}
        dpi_map = {}
        
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            try:
                complexity = self.complexity_analyzer.analyze_page(pdf_path, page_num)
                complexity_results[page_num] = complexity
                
                # DPI 결정
                if complexity["has_table"] or complexity["complexity_score"] >= 0.3:
                    dpi_map[page_num] = 300
                else:
                    dpi_map[page_num] = 150
                    
            except Exception as e:
                logger.error(f"페이지 {page_num} 복잡도 분석 실패: {e}")
                complexity_results[page_num] = {"complexity_score": 0.1, "has_table": False}
                dpi_map[page_num] = 150
        
        # 2. Vision LLM 호출 병렬 처리
        semaphore = asyncio.Semaphore(self.max_concurrency)
        token_tracker = TokenTracker()
        token_tracker_lock = asyncio.Lock()
        
        async def process_page(page_idx: int) -> Optional[Dict[str, Any]]:
            """단일 페이지 처리 (비동기, 동적 DPI)."""
            page_num = page_idx + 1
            
            async with semaphore:  # 동시 실행 수 제한
                try:
                    complexity = complexity_results[page_num]
                    dpi = dpi_map[page_num]
                    
                    # 동적 렌더링
                    page_data = self.renderer.render_page_with_dpi(pdf_path, page_idx, dpi)
                    
                    # Vision 추출 (비동기)
                    extraction = await self.vision_router.route_and_extract_async(
                        image_base64=page_data["image_base64"],
                        page_num=page_num,
                        complexity_score=complexity["complexity_score"],
                        system_prompt=StructureExtractor.SYSTEM_PROMPT
                    )
                    
                    # 토큰 사용량 추적 (스레드 안전)
                    tokens_used = extraction.get("tokens_used", 0)
                    async with token_tracker_lock:
                        token_tracker.add_usage(page_num, extraction["model_used"], tokens_used)
                        
                        # 예산 확인
                        if not token_tracker.check_budget(self.token_budget):
                            logger.warning(
                                f"토큰 예산 초과: {token_tracker.total_tokens}/{self.token_budget}. "
                                f"페이지 {page_num} 처리 중단."
                            )
                            return None
                    
                    # 구조화 (동기, 빠르므로 순차 처리)
                    structure = self.structure_extractor.extract(
                        extraction["content"],
                        page_num
                    )
                    
                    result = {
                        "page_num": page_num,
                        "model_used": extraction["model_used"],
                        "complexity_score": complexity["complexity_score"],
                        "has_table": complexity.get("has_table", False),
                        "dpi": dpi,  # DPI 기록
                        "structure": structure.dict(),
                        "tokens_used": tokens_used
                    }
                    
                    logger.debug(f"페이지 {page_num} 완료: {dpi} DPI, {tokens_used} 토큰 ({extraction['model_used']})")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"페이지 {page_num} 실패: {e}", exc_info=True)
                    return None
        
        # 모든 페이지 병렬 처리
        tasks = [process_page(i) for i in range(total_pages)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 정리 (None과 예외 제거, 페이지 번호 순 정렬)
        vision_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"페이지 처리 중 예외 발생: {result}")
            elif result is not None:
                vision_results.append(result)
        
        # 페이지 번호 순 정렬
        vision_results.sort(key=lambda x: x["page_num"])
        
        logger.info(
            f"Phase 1 완료: {len(vision_results)}/{total_pages}개 페이지 처리. "
            f"총 토큰: {token_tracker.total_tokens} "
            f"({token_tracker.get_summary()['tokens_by_model']})"
        )
        
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
