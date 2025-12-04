"""
module: vision_batch.py
description: 여러 PDF 파일의 배치 처리 관리자 (파일 레벨 배치)
author: AI Agent
created: 2025-01-14

Note: 
- 이 모듈은 여러 PDF 파일들의 순차 처리를 담당 (파일 레벨 배치)
- structure_extractor.extract_batch()는 단일 PDF 내 페이지들의 LLM 배치 (페이지 레벨 배치)
- 두 배치는 레벨이 다르므로 역할 분리 유지
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .vision_orchestrator import VisionOrchestrator

logger = logging.getLogger(__name__)


class BatchResult:
    """배치 처리 결과 관리."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
    
    def add_result(self, file_name: str, status: str, error: str = None, **kwargs):
        """개별 파일 처리 결과 추가."""
        self.results.append({
            "file": file_name,
            "status": status,
            "error": error,
            **kwargs
        })
    
    def finalize(self):
        """배치 처리 완료."""
        self.end_time = datetime.now()
    
    def get_summary(self) -> Dict[str, Any]:
        """배치 처리 요약 반환."""
        success_count = sum(1 for r in self.results if r["status"] == "success")
        failed_files = [r["file"] for r in self.results if r["status"] != "success"]
        
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return {
            "total_files": len(self.results),
            "success_count": success_count,
            "failed_count": len(self.results) - success_count,
            "failed_files": failed_files,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


class VisionBatchProcessor:
    """여러 PDF 파일의 배치 처리 관리자."""
    
    def __init__(self, orchestrator: VisionOrchestrator):
        """
        Args:
            orchestrator: VisionOrchestrator 인스턴스
        """
        self.orchestrator = orchestrator
    
    def collect_pdf_files(self, pdf_path: Optional[str] = None, folder_path: Optional[str] = None, 
                         project_root: Path = None) -> List[Path]:
        """
        PDF 파일 목록 수집.
        
        Args:
            pdf_path: 단일 PDF 파일 경로
            folder_path: 폴더 경로 (전체 PDF 처리)
            project_root: 프로젝트 루트 경로
            
        Returns:
            처리할 PDF 파일 경로 리스트
        """
        pdf_files = []
        
        if pdf_path:
            # 단일 파일 지정
            pdf_file = Path(pdf_path)
            if not pdf_file.is_absolute() and project_root:
                pdf_file = project_root / pdf_file
            
            if pdf_file.exists():
                pdf_files = [pdf_file]
            else:
                logger.error(f"❌ PDF 파일 없음: {pdf_file}")
                
        elif folder_path:
            # 폴더 전체 처리
            folder = Path(folder_path)
            if not folder.is_absolute() and project_root:
                folder = project_root / folder
            
            if not folder.exists():
                logger.error(f"❌ 폴더 없음: {folder}")
                return []
            
            pdf_files = sorted(folder.glob("*.pdf"))
            pdf_files = [p for p in pdf_files if not p.name.startswith(".")]
        
        return pdf_files
    
    async def process_single_pdf(self, pdf_path: Path, use_parallel: bool = True) -> Dict[str, Any]:
        """
        단일 PDF 처리.
        
        Args:
            pdf_path: PDF 파일 경로
            use_parallel: 병렬 처리 사용 여부
            
        Returns:
            처리 결과
        """
        logger.info("=" * 60)
        logger.info(f"🚀 처리 시작: {pdf_path.name}")
        logger.info("=" * 60)
        
        try:
            result = await asyncio.to_thread(
                self.orchestrator.process_pdf, str(pdf_path), use_parallel
            )
            
            if result["status"] == "success":
                vision_results = result.get("vision_extraction_result", [])
                total_tokens = sum(p.get("tokens_used", 0) for p in vision_results)
                
                logger.info(f"✅ 완료: {len(vision_results)}페이지, {total_tokens:,}토큰")
            else:
                logger.error(f"❌ 실패: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.exception(f"❌ PDF 처리 중 예외 발생: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def process_batch(self, pdf_files: List[Path], use_parallel: bool = True, 
                          progress_callback: Optional[callable] = None) -> BatchResult:
        """
        여러 PDF 파일 배치 처리.
        
        Args:
            pdf_files: 처리할 PDF 파일 리스트
            use_parallel: 개별 PDF 내 페이지 병렬 처리 여부
            progress_callback: 진행 상황 콜백 함수
            
        Returns:
            BatchResult 객체
        """
        if not pdf_files:
            logger.error("❌ 처리할 PDF 파일이 없습니다")
            return BatchResult()
        
        logger.info(f"📚 총 {len(pdf_files)}개 PDF 파일 배치 처리 시작")
        
        batch_result = BatchResult()
        
        # 순차 처리 (파일 레벨)
        for idx, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n[{idx}/{len(pdf_files)}] {pdf_path.name}")
            
            # 진행 상황 콜백 호출
            if progress_callback:
                progress_callback(idx, len(pdf_files), pdf_path.name)
            
            # 개별 PDF 처리
            result = await self.process_single_pdf(pdf_path, use_parallel)
            
            # 결과 기록
            if result["status"] == "success":
                vision_results = result.get("vision_extraction_result", [])
                total_tokens = sum(p.get("tokens_used", 0) for p in vision_results)
                
                batch_result.add_result(
                    file_name=pdf_path.name,
                    status="success",
                    pages_processed=len(vision_results),
                    total_tokens=total_tokens
                )
            else:
                batch_result.add_result(
                    file_name=pdf_path.name,
                    status="error",
                    error=result.get("error")
                )
        
        batch_result.finalize()
        return batch_result
    
    def print_batch_summary(self, batch_result: BatchResult, output_dir: Optional[Path] = None):
        """배치 처리 요약 출력."""
        summary = batch_result.get_summary()
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 배치 처리 완료")
        logger.info("=" * 60)
        
        logger.info(f"전체 파일: {summary['total_files']}")
        logger.info(f"성공: {summary['success_count']}")
        logger.info(f"실패: {summary['failed_count']}")
        
        if summary['duration_seconds']:
            logger.info(f"처리 시간: {summary['duration_seconds']:.1f}초")
        
        # 성공률 계산
        if summary['total_files'] > 0:
            success_rate = (summary['success_count'] / summary['total_files']) * 100
            logger.info(f"성공률: {success_rate:.1f}%")
        
        # 실패 파일 목록
        if summary['failed_files']:
            logger.info("\n실패 파일:")
            for file_name in summary['failed_files']:
                logger.info(f"  - {file_name}")
        
        # 토큰 사용량 통계
        total_tokens = sum(
            r.get("total_tokens", 0) for r in batch_result.results 
            if r["status"] == "success"
        )
        total_pages = sum(
            r.get("pages_processed", 0) for r in batch_result.results 
            if r["status"] == "success"
        )
        
        if total_tokens > 0:
            logger.info(f"\n📊 토큰 사용량:")
            logger.info(f"  총 토큰: {total_tokens:,}")
            logger.info(f"  총 페이지: {total_pages}")
            if total_pages > 0:
                avg_tokens = total_tokens / total_pages
                logger.info(f"  페이지당 평균: {avg_tokens:.0f} 토큰")
        
        # 출력 디렉토리 안내
        if output_dir and output_dir.exists():
            logger.info(f"\n📁 출력 위치: {output_dir}")