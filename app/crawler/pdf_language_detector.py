"""
PDF 언어 감지 모듈
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List, Optional
import logging
from .cleaner import get_language_detector

logger = logging.getLogger(__name__)


class PDFLanguageDetector:
    """PDF 문서의 언어를 감지하는 클래스"""
    
    def __init__(self):
        self.language_detector = get_language_detector()
    
    def get_sample_pages(self, total_pages: int) -> List[int]:
        """
        페이지 샘플링 규칙에 따라 중간 3장을 선택
        
        Args:
            total_pages: 전체 페이지 수
            
        Returns:
            샘플링할 페이지 인덱스 리스트 (0부터 시작)
        """
        if total_pages >= 5:
            # 중간 페이지 기준 3장 선택
            mid = total_pages // 2
            return [mid - 1, mid, mid + 1]
        elif total_pages == 4:
            # 중간부에 가까운 3장 사용
            return [1, 2, 3]
        elif total_pages == 3:
            # 전체 3장 사용
            return [0, 1, 2]
        else:
            # total_pages < 3: 전체 페이지 사용
            return list(range(total_pages))
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, any]:
        """
        PDF에서 샘플 페이지의 텍스트를 추출
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            추출된 텍스트와 메타데이터
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            if total_pages == 0:
                return {
                    'success': False,
                    'error': 'PDF has no pages',
                    'total_pages': 0,
                    'sample_pages': [],
                    'text': ''
                }
            
            sample_pages = self.get_sample_pages(total_pages)
            extracted_texts = []
            
            for page_idx in sample_pages:
                if page_idx < total_pages:
                    page = doc[page_idx]
                    text = page.get_text()
                    if text.strip():
                        extracted_texts.append(text)
            
            doc.close()
            
            combined_text = ' '.join(extracted_texts)
            
            return {
                'success': True,
                'total_pages': total_pages,
                'sample_pages': sample_pages,
                'text': combined_text,
                'text_length': len(combined_text)
            }
            
        except Exception as e:
            logger.error(f"PDF 텍스트 추출 실패 ({pdf_path}): {e}")
            return {
                'success': False,
                'error': str(e),
                'total_pages': 0,
                'sample_pages': [],
                'text': ''
            }
    
    def detect_document_language(self, text: str) -> Dict[str, any]:
        """
        샘플링된 텍스트를 기반으로 문서의 주 언어를 감지
        
        Args:
            text: 샘플링된 텍스트
            
        Returns:
            언어 감지 결과
        """
        if not text or len(text.strip()) < 10:
            return {
                'language_code': 'UNKNOWN',
                'language_name': 'Unknown',
                'confidence': 0.0,
                'is_reliable': False
            }
        
        result = self.language_detector.detect_language(text)
        
        return {
            'language_code': result.get('language_code', 'UNKNOWN'),
            'language_name': result.get('language_name', 'Unknown'),
            'confidence': result.get('confidence', 0.0),
            'is_reliable': result.get('is_reliable', False)
        }
    
    def process_pdf(self, pdf_path: str) -> Dict[str, any]:
        """
        PDF 파일을 처리하여 언어를 감지
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            처리 결과
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            return {
                'file_path': str(pdf_path),
                'success': False,
                'error': 'File not found',
                'language_code': 'ERROR',
                'language_name': 'Error'
            }
        
        # 텍스트 추출
        extraction_result = self.extract_text_from_pdf(str(pdf_path))
        
        if not extraction_result['success']:
            return {
                'file_path': str(pdf_path),
                'success': False,
                'error': extraction_result['error'],
                'language_code': 'ERROR',
                'language_name': 'Error'
            }
        
        # 언어 감지
        language_result = self.detect_document_language(extraction_result['text'])
        
        return {
            'file_path': str(pdf_path),
            'success': True,
            'total_pages': extraction_result['total_pages'],
            'sample_pages': extraction_result['sample_pages'],
            'text_length': extraction_result['text_length'],
            'language_code': language_result['language_code'],
            'language_name': language_result['language_name'],
            'confidence': language_result['confidence'],
            'is_reliable': language_result['is_reliable']
        }


def detect_pdf_language(pdf_path: str) -> Dict[str, any]:
    """
    PDF 파일의 언어를 감지하는 편의 함수
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        언어 감지 결과
    """
    detector = PDFLanguageDetector()
    return detector.process_pdf(pdf_path)