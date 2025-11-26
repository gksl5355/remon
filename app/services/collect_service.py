"""
데이터 수집 서비스
"""

import logging
from pathlib import Path
from datetime import datetime
import hashlib
import json

# 기존 임포트 유지
# from ... import ...

# 언어 탐지 관련 임포트 추가
from app.crawler.cleaner import get_language_detector, get_text_cleaner
from utils.text_utils import save_metadata

logger = logging.getLogger(__name__)


class CollectService:
    """문서 수집 및 처리 서비스"""
    
    def __init__(self):
        # 기존 초기화 코드 유지
        # ...
        
        # 언어 탐지기 추가
        self.language_detector = get_language_detector()
        self.text_cleaner = get_text_cleaner()
    
    def process_document(
        self,
        pdf_path: str,
        output_dir: str,
        country_code: str = None,
        **kwargs
    ) -> dict:
        """
        새 규제 문서 처리 (언어 탐지 포함)
        
        Args:
            pdf_path: PDF 파일 경로
            output_dir: 출력 디렉토리
            country_code: 국가 코드
            **kwargs: 추가 메타데이터
            
        Returns:
            처리 결과
        """
        logger.info(f"문서 처리 시작: {pdf_path}")
        
        # 1. 기존 PDF 처리 로직 (유지)
        # text_content = self._extract_text_from_pdf(pdf_path)
        # ... 기존 코드 ...
        
        # 2. 문서 ID 생성
        document_id = kwargs.get('document_id', self._generate_document_id(pdf_path))
        
        # 3. 텍스트 파일 저장
        text_file_path = Path(output_dir) / f"{document_id}.txt"
        # with open(text_file_path, 'w', encoding='utf-8') as f:
        #     f.write(text_content)
        
        # 4. 언어 탐지 (새로 추가)
        text_content = text_file_path.read_text(encoding='utf-8')
        lang_info = self.language_detector.detect_language(text_content)
        
        # 국가 정보가 있으면 검증
        if country_code:
            lang_info = self.language_detector.validate_with_country(
                lang_info, 
                country_code
            )
        
        logger.info(
            f"언어 탐지: {lang_info['language_code']} "
            f"(신뢰도: {lang_info.get('confidence', 0):.2%})"
        )
        
        # 5. 메타데이터 생성 (언어 정보 포함)
        metadata = self._create_metadata_with_language(
            pdf_path=pdf_path,
            text_content=text_content,
            country_code=country_code,
            language_info=lang_info,
            **kwargs
        )
        
        # 6. 메타데이터 저장
        metadata_path = Path(output_dir) / f"{document_id}_metadata.json"
        save_metadata(metadata, str(metadata_path))
        
        logger.info(f"문서 처리 완료: {document_id}")
        
        return {
            'document_id': document_id,
            'text_file': str(text_file_path),
            'metadata_file': str(metadata_path),
            'language': lang_info['language_code'],
            'confidence': lang_info.get('confidence', 0)
        }
    
    def _create_metadata_with_language(
        self,
        pdf_path: str,
        text_content: str,
        country_code: str,
        language_info: dict,
        **kwargs
    ) -> dict:
        """
        언어 정보를 포함한 메타데이터 생성
        
        Args:
            pdf_path: PDF 파일 경로
            text_content: 텍스트 내용
            country_code: 국가 코드
            language_info: 언어 탐지 결과
            **kwargs: 추가 메타데이터
            
        Returns:
            메타데이터 딕셔너리
        """
        pdf_file = Path(pdf_path)
        
        metadata = {
            'document_id': kwargs.get('document_id', ''),
            'text_file': kwargs.get('text_file', f"{pdf_file.stem}.txt"),
            'metadata': {
                'file_info': {
                    'original_filename': pdf_file.name,
                    'original_path': str(pdf_path),
                    'file_size_bytes': pdf_file.stat().st_size if pdf_file.exists() else 0,
                    'extracted_date': datetime.now().isoformat(),
                    'document_hash': hashlib.sha256(text_content.encode()).hexdigest()
                },
                
                # 기본 정보
                'country_code': country_code,
                'country': kwargs.get('country', ''),
                'source': kwargs.get('source', ''),
                'agency': kwargs.get('agency', ''),
                
                # 언어 정보 (새로 추가)
                'language_code': language_info['language_code'],
                'language_detection': {
                    'detected_language': language_info['language_code'],
                    'language_name': language_info.get('language_name', ''),
                    'confidence': language_info.get('confidence', 0.0),
                    'is_reliable': language_info.get('is_reliable', False),
                    'method': language_info.get('method', 'content_analysis'),
                    'detection_timestamp': datetime.now().isoformat(),
                    'confidence_scores': language_info.get('confidence_scores', {}),
                    'validation': language_info.get('validation', {})
                },
                
                # 통계
                'text_length': len(text_content),
                'word_count': len(text_content.split()),
                
                # 기타 기존 필드들
                'version_number': kwargs.get('version_number', 1),
                'is_initial_version': kwargs.get('is_initial_version', True),
            }
        }
        
        return metadata
    
    # 기존 메서드들 유지
    # def _extract_text_from_pdf(self, pdf_path: str) -> str:
    #     ...
    # def _generate_document_id(self, pdf_path: str) -> str:
    #     ...