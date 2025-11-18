"""
텍스트 처리 유틸리티 함수
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def update_metadata_with_language(
    metadata_path: str,
    text_file_path: str,
    language_detector,
    country_code: Optional[str] = None,
    backup: bool = True
) -> Dict:
    """
    메타데이터 파일에 언어 정보 추가/업데이트
    
    Args:
        metadata_path: 메타데이터 JSON 파일 경로
        text_file_path: 텍스트 파일 경로
        language_detector: LanguageDetector 인스턴스
        country_code: 국가 코드 (검증용)
        backup: 원본 백업 여부
        
    Returns:
        업데이트된 메타데이터
    """
    metadata_path = Path(metadata_path)
    text_file_path = Path(text_file_path)
    
    # 1. 기존 메타데이터 로드
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        logger.error(f"메타데이터 로드 실패: {e}")
        raise
    
    # 2. 백업 생성
    if backup:
        backup_path = metadata_path.with_suffix('.json.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # 3. 기존 language_code 백업
    if 'metadata' in metadata and 'language_code' in metadata['metadata']:
        original_lang = metadata['metadata']['language_code']
        metadata['metadata']['language_code_original'] = original_lang
    
    # 4. 텍스트 읽기 및 언어 탐지
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        # fallback 인코딩 시도
        for encoding in ['cp949', 'latin-1', 'utf-16']:
            try:
                with open(text_file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                break
            except:
                continue
    
    lang_result = language_detector.detect_language(text)
    
    # 5. 국가 기반 검증
    if country_code:
        lang_result = language_detector.validate_with_country(lang_result, country_code)
    
    # 6. 메타데이터 업데이트
    if 'metadata' not in metadata:
        metadata['metadata'] = {}
    
    metadata['metadata']['language_code'] = lang_result['language_code']
    metadata['metadata']['language_detection'] = {
        'detected_language': lang_result['language_code'],
        'language_name': lang_result.get('language_name', 'Unknown'),
        'confidence': lang_result.get('confidence', 0.0),
        'is_reliable': lang_result.get('is_reliable', False),
        'method': lang_result.get('method', 'unknown'),
        'detection_timestamp': datetime.now().isoformat(),
        'confidence_scores': lang_result.get('confidence_scores', {}),
        'validation': lang_result.get('validation', {})
    }
    
    if 'error' in lang_result:
        metadata['metadata']['language_detection']['error'] = lang_result['error']
    
    return metadata


def save_metadata(metadata: Dict, output_path: str):
    """
    메타데이터를 JSON 파일로 저장
    
    Args:
        metadata: 메타데이터 딕셔너리
        output_path: 저장 경로
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"메타데이터 저장: {output_path}")
    except Exception as e:
        logger.error(f"메타데이터 저장 실패: {e}")
        raise


def load_metadata(metadata_path: str) -> Dict:
    """
    메타데이터 파일 로드
    
    Args:
        metadata_path: 메타데이터 파일 경로
        
    Returns:
        메타데이터 딕셔너리
    """
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"메타데이터 로드 실패: {e}")
        raise


def extract_text_sample(text: str, max_length: int = 5000) -> str:
    """
    텍스트 샘플 추출
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        
    Returns:
        샘플 텍스트
    """
    if len(text) <= max_length:
        return text
    
    # 앞, 중간, 끝에서 균등하게 추출
    chunk = max_length // 3
    start = text[:chunk]
    middle_pos = len(text) // 2 - chunk // 2
    middle = text[middle_pos:middle_pos + chunk]
    end = text[-chunk:]
    
    return start + " " + middle + " " + end
