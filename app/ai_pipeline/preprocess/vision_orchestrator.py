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
        self.max_concurrency = max_concurrency or 30
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
                Path(pdf_path).name,
                vision_results=vision_results
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
        
        # 1. 모든 페이지 정보 수집 (복잡도, DPI, 모델 결정)
        page_infos = self._prepare_page_infos(pdf_path, total_pages)
        
        # 2. 모델별 배치 생성
        batches = self._create_model_batches(page_infos)
        
        # 3. 배치별 병렬 처리
        token_tracker = TokenTracker()
        token_tracker_lock = asyncio.Lock()
        
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def process_batch(batch: Dict[str, Any]) -> List[Dict[str, Any]]:
            """단일 배치 처리 (비동기)."""
            async with semaphore:
                try:
                    model_name = batch["model_name"]
                    pages = batch["pages"]
                    
                    logger.info(f"배치 처리 시작: {model_name}, {len(pages)}페이지 (페이지 {[p['page_index']+1 for p in pages]})")
                    
                    # 배치 단위 Vision 호출
                    batch_results = await asyncio.to_thread(
                        self.structure_extractor.extract_batch,
                        pages,
                        model_name
                    )
                    
                    # 토큰 사용량 추적
                    total_batch_tokens = sum(r.get("tokens_used", 0) for r in batch_results)
                    async with token_tracker_lock:
                        for result in batch_results:
                            page_num = result["page_num"]
                            tokens_used = result.get("tokens_used", 0)
                            token_tracker.add_usage(page_num, model_name, tokens_used)
                        
                        # 예산 확인
                        if not token_tracker.check_budget(self.token_budget):
                            logger.warning(
                                f"토큰 예산 초과: {token_tracker.total_tokens}/{self.token_budget}. "
                                f"배치 처리 중단."
                            )
                            return []
                    
                    logger.info(f"배치 완료: {model_name}, {len(batch_results)}페이지, {total_batch_tokens}토큰")
                    return batch_results
                    
                except Exception as e:
                    logger.error(f"배치 처리 실패 ({batch['model_name']}): {e}", exc_info=True)
                    return []
        
        # 모든 배치 병렬 처리
        logger.info(f"총 {len(batches)}개 배치 생성: {[(b['model_name'], len(b['pages'])) for b in batches]}")
        
        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # 결과 병합 및 정리
        all_results = []
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                logger.error(f"배치 처리 중 예외 발생: {batch_result}")
            elif batch_result:
                all_results.extend(batch_result)
        
        # 페이지 번호 순 정렬
        all_results.sort(key=lambda x: x["page_num"])
        
        # 기존 형식으로 변환 (외부 호환성 유지)
        vision_results = []
        for result in all_results:
            page_info = next((p for p in page_infos if p["page_index"] == result["page_index"]), {})
            
            vision_results.append({
                "page_num": result["page_num"],
                "model_used": result["model_used"],
                "complexity_score": result["complexity_score"],
                "has_table": page_info.get("has_table", False),
                "dpi": page_info.get("dpi", 150),
                "structure": result["structure"],
                "tokens_used": result["tokens_used"]
            })
        
        logger.info(
            f"Phase 1 완료: {len(vision_results)}/{total_pages}개 페이지 처리. "
            f"총 토큰: {token_tracker.total_tokens} "
            f"({token_tracker.get_summary()['tokens_by_model']})"
        )
        
        return vision_results
    
    def _prepare_page_infos(self, pdf_path: str, total_pages: int) -> List[Dict[str, Any]]:
        """모든 페이지 정보 수집 (복잡도, DPI, 모델 결정)."""
        page_infos = []
        
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            
            try:
                # 복잡도 분석
                complexity = self.complexity_analyzer.analyze_page(pdf_path, page_num)
                
                # DPI 결정
                if complexity["has_table"] or complexity["complexity_score"] >= 0.3:
                    dpi = 300
                else:
                    dpi = 150
                
                # 모델 결정 (기존 VisionRouter 로직 재사용)
                if complexity["complexity_score"] >= self.vision_router.complexity_threshold:
                    model_name = self.vision_router.model_complex
                else:
                    model_name = self.vision_router.model_simple
                
                # 페이지 렌더링
                page_data = self.renderer.render_page_with_dpi(pdf_path, page_idx, dpi)
                
                page_info = {
                    "page_index": page_idx,
                    "page_num": page_num,
                    "image_base64": page_data["image_base64"],
                    "complexity": complexity["complexity_score"],
                    "has_table": complexity["has_table"],
                    "dpi": dpi,
                    "model_name": model_name
                }
                
                page_infos.append(page_info)
                
                logger.info(f"페이지 {page_num}: 복잡도 {complexity['complexity_score']:.2f} → {dpi} DPI")
                
            except Exception as e:
                logger.error(f"페이지 {page_num} 정보 수집 실패: {e}")
                # Fallback 정보
                page_infos.append({
                    "page_index": page_idx,
                    "page_num": page_num,
                    "image_base64": "",
                    "complexity": 0.1,
                    "has_table": False,
                    "dpi": 150,
                    "model_name": self.vision_router.model_simple
                })
        
        return page_infos
    
    def _create_model_batches(self, page_infos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """모델별 배치 생성."""
        from .config import PreprocessConfig
        
        config = PreprocessConfig.get_vision_config()
        batch_size_simple = config["batch_size_simple"]
        batch_size_complex = config["batch_size_complex"]
        
        # 모델별 그룹핑
        model_groups = {}
        for page_info in page_infos:
            model_name = page_info["model_name"]
            if model_name not in model_groups:
                model_groups[model_name] = []
            model_groups[model_name].append(page_info)
        
        # 배치 생성
        batches = []
        for model_name, pages in model_groups.items():
            # 배치 크기 결정
            if "4o-mini" in model_name or "mini" in model_name:
                batch_size = batch_size_simple
            else:
                batch_size = batch_size_complex
            
            # 페이지를 배치 크기로 분할
            for i in range(0, len(pages), batch_size):
                batch_pages = pages[i:i + batch_size]
                batches.append({
                    "model_name": model_name,
                    "pages": batch_pages
                })
        
        logger.info(
            f"배치 생성 완료: {len(batches)}개 배치. "
            f"모델별 페이지 수: {[(model, len(pages)) for model, pages in model_groups.items()]}"
        )
        
        return batches
    
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
        source_file: str,
        vision_results: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Phase 4: Qdrant + Graph 저장 (regulation_id 자동 생성)."""
        logger.info("Phase 4: Dual Indexing 시작")
        
        import re
        from pathlib import Path
        
        # regulation_id 생성 전략
        regulation_id = None
        
        # 전략 1: 메타데이터에서 추출
        if vision_results:
            first_page = vision_results[0]
            metadata = first_page.get("structure", {}).get("metadata", {})
            
            title = metadata.get("title", "")
            country = metadata.get("country", "")
            regulation_type = metadata.get("regulation_type", "")
            
            # title + country + type 조합으로 ID 생성
            if title:
                # 예: "FDA-US-Required-Warnings-Cigarette"
                parts = []
                if regulation_type:
                    parts.append(regulation_type)
                if country:
                    parts.append(country)
                # title에서 주요 단어 추출 (3개)
                title_words = re.findall(r'\b[A-Z][a-z]+\b', title)[:3]
                parts.extend(title_words)
                
                if parts:
                    regulation_id = "-".join(parts)
                    logger.info(f"regulation_id 생성 (메타데이터): {regulation_id}")
        
        # 전략 2: 파일명 기반 (fallback)
        if not regulation_id:
            file_stem = Path(source_file).stem
            regulation_id = re.sub(r'[^A-Za-z0-9-]', '-', file_stem)
            logger.info(f"regulation_id 생성 (파일명): {regulation_id}")
        
        summary = self.dual_indexer.index(
            chunks=chunks, 
            graph_data=graph_data, 
            source_file=source_file,
            regulation_id=regulation_id,
            vision_results=vision_results
        )
        
        logger.info(f"Phase 4 완료: {summary['qdrant_chunks']}개 청크 저장 (ref_blocks: {summary.get('reference_blocks_count', 0)})")
        
        return summary
