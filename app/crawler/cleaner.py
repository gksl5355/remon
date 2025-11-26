"""
텍스트 정제 및 언어 탐지 모듈
"""

from lingua import Language, LanguageDetectorBuilder
from typing import Optional, Dict, List
import logging
import re

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    규제 문서의 언어를 자동 탐지하는 클래스
    """
    
    # 규제 문서에서 주로 사용되는 언어
    REGULATION_LANGUAGES = [
        Language.ENGLISH, Language.KOREAN, Language.JAPANESE,
        Language.CHINESE, Language.GERMAN, Language.FRENCH,
        Language.SPANISH, Language.PORTUGUESE, Language.RUSSIAN,
        Language.ITALIAN, Language.DUTCH, Language.POLISH,
        Language.TURKISH, Language.VIETNAMESE, Language.THAI,
        Language.INDONESIAN, Language.ARABIC,
    ]
    
    _instance = None  # 싱글톤 인스턴스
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """언어 탐지기 초기화 (최초 1회만)"""
        if self._initialized:
            return
        
        logger.info("언어 탐지기 초기화 중...")
        
        self.detector = LanguageDetectorBuilder.from_languages(*self.REGULATION_LANGUAGES)\
            .with_preloaded_language_models()\
            .build()
        
        self._initialized = True
        logger.info("언어 탐지기 초기화 완료")
    
    def detect_language(
        self, 
        text: str, 
        sample_size: int = 3000,
        min_confidence: float = 0.7
    ) -> Dict[str, any]:
        """
        텍스트에서 언어 탐지
        
        Args:
            text: 분석할 텍스트
            sample_size: 샘플링할 최대 문자 수
            min_confidence: 최소 신뢰도 임계값
            
        Returns:
            언어 탐지 결과 딕셔너리
        """
        if not text or len(text.strip()) < 10:
            logger.warning("텍스트가 너무 짧아 언어 탐지 불가")
            return {
                'language_code': 'UNKNOWN',
                'language_name': 'Unknown',
                'confidence': 0.0,
                'method': 'insufficient_text',
                'is_reliable': False
            }
        
        try:
            # 긴 문서의 경우 샘플링
            sample_text = self._sample_text(text, sample_size)
            
            # 언어 탐지
            detected_language = self.detector.detect_language_of(sample_text)
            
            if not detected_language:
                return {
                    'language_code': 'UNKNOWN',
                    'language_name': 'Unknown',
                    'confidence': 0.0,
                    'method': 'detection_failed',
                    'is_reliable': False
                }
            
            # 신뢰도 계산
            confidence_values = self.detector.compute_language_confidence_values(sample_text)
            confidence_dict = {c.language.name: c.value for c in confidence_values}
            
            top_confidence = confidence_dict.get(detected_language.name, 0.0)
            iso_code = detected_language.iso_code_639_1.name.upper()
            
            result = {
                'language_code': iso_code,
                'language_name': detected_language.name,
                'confidence': round(top_confidence, 4),
                'method': 'content_analysis',
                'is_reliable': top_confidence >= min_confidence,
                'sample_length': len(sample_text),
                'confidence_scores': {
                    lang: round(score, 4) 
                    for lang, score in sorted(
                        confidence_dict.items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:3]
                }
            }
            
            logger.info(f"언어 탐지: {iso_code} (신뢰도: {top_confidence:.2%})")
            return result
            
        except Exception as e:
            logger.error(f"언어 탐지 중 오류: {e}", exc_info=True)
            return {
                'language_code': 'ERROR',
                'language_name': 'Error',
                'confidence': 0.0,
                'method': 'error',
                'is_reliable': False,
                'error': str(e)
            }
    
    def _sample_text(self, text: str, max_chars: int) -> str:
        """긴 텍스트를 샘플링"""
        if len(text) <= max_chars:
            return text
        
        chunk_size = max_chars // 3
        start = text[:chunk_size]
        middle_pos = len(text) // 2 - chunk_size // 2
        middle = text[middle_pos:middle_pos + chunk_size]
        end = text[-chunk_size:]
        
        return start + " " + middle + " " + end
    
    def validate_with_country(
        self,
        detected_lang: Dict[str, any],
        country_code: Optional[str] = None
    ) -> Dict[str, any]:
        """
        탐지된 언어를 국가 정보와 비교하여 검증
        
        Args:
            detected_lang: 탐지된 언어 정보
            country_code: 문서 발행 국가 코드
            
        Returns:
            검증된 언어 정보
        """
        result = detected_lang.copy()
        result['validation'] = {'country_match': False, 'override_reason': None}
        
        if not country_code:
            return result
        
        # 국가별 주요 언어 매핑
        country_lang_map = {
            'US': 'EN', 'GB': 'EN', 'CA': 'EN', 'AU': 'EN',
            'KR': 'KO', 'JP': 'JA', 'CN': 'ZH', 'TW': 'ZH',
            'DE': 'DE', 'FR': 'FR', 'ES': 'ES', 'BR': 'PT',
            'RU': 'RU', 'IT': 'IT', 'NL': 'NL', 'PL': 'PL',
            'TR': 'TR', 'VN': 'VI', 'TH': 'TH', 'ID': 'ID',
            'SA': 'AR', 'AE': 'AR', 'EG': 'AR',
        }
        
        expected_lang = country_lang_map.get(country_code.upper())
        
        if expected_lang == detected_lang['language_code']:
            result['validation']['country_match'] = True
        
        # 신뢰도가 낮고 국가 정보가 있으면 국가 기반으로 보정
        if not detected_lang.get('is_reliable', False) and expected_lang:
            result['language_code'] = expected_lang
            result['validation']['override_reason'] = 'low_confidence_country_fallback'
            logger.info(f"신뢰도 낮음, 국가 기반 보정: {expected_lang}")
        
        return result


class TextCleaner:
    """
    텍스트 정제 클래스 (기존 cleaner.py의 기능 유지)
    """
    
    def __init__(self):
        self.language_detector = LanguageDetector()
    
    def clean_text(self, text: str) -> str:
        """
        텍스트 정제
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정제된 텍스트
        """
        # 연속된 공백 제거
        cleaned = ' '.join(text.split())
        
        # 특수 문자 정규화 (기존 로직 유지)
        # ... 기존 정제 로직 추가 ...
        
        return cleaned
    
    def clean_and_detect_language(
        self, 
        text: str,
        country_code: Optional[str] = None
    ) -> Dict[str, any]:
        """
        텍스트 정제 및 언어 탐지를 동시에 수행
        
        Args:
            text: 원본 텍스트
            country_code: 국가 코드 (선택)
            
        Returns:
            정제된 텍스트와 언어 정보
        """
        cleaned_text = self.clean_text(text)
        lang_info = self.language_detector.detect_language(cleaned_text)
        
        if country_code:
            lang_info = self.language_detector.validate_with_country(lang_info, country_code)
        
        return {
            'cleaned_text': cleaned_text,
            'language_info': lang_info
        }


# 싱글톤 인스턴스 반환 함수
def get_language_detector() -> LanguageDetector:
    """언어 탐지기 싱글톤 인스턴스 반환"""
    return LanguageDetector()


def get_text_cleaner() -> TextCleaner:
    """텍스트 정제기 인스턴스 반환"""
    return TextCleaner()
