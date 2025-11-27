"""
module: definition_extractor.py
description: 청킹 전략에 통합된 정의 및 약어 추출기
author: AI Agent
created: 2025-11-12
updated: 2025-11-18
dependencies:
    - re, logging, json
"""

import re
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class DefinitionExtractor:
    """
    청킹 전략에 통합된 정의 및 약어 추출기 (미국 규제 전용).
    
    역할:
    - 용어 정의 감지 ("means", "is defined as")
    - 약어 감지 (FDA, CFR 등)
    - 청킹 시 정의 영역 보존
    - 담배 규제 도메인 특화 용어 정규화
    """
    
    # 담배 규제 도메인 특화 용어 사전
    TOBACCO_TERMS_DICT = {
        # 기관 및 법률
        "FDA": "Food and Drug Administration (FDA)",
        "CFR": "Code of Federal Regulations (CFR)",
        "USC": "United States Code (USC)",
        "FR": "Federal Register (FR)",
        "FFDCA": "Federal Food, Drug, and Cosmetic Act (FFDCA)",
        "FSPTCA": "Family Smoking Prevention and Tobacco Control Act (FSPTCA)",
        
        # 담배 제품 관련
        "HPHC": "Harmful and Potentially Harmful Constituent (HPHC)",
        "MRTP": "Modified Risk Tobacco Product (MRTP)",
        "VLNC": "Very Low Nicotine Content (VLNC)",
        "PMTA": "Premarket Tobacco Application (PMTA)",
        "SE": "Substantial Equivalence (SE)",
        "ENDS": "Electronic Nicotine Delivery Systems (ENDS)",
        
        # 화학 성분
        "TPM": "Total Particulate Matter (TPM)",
        "NFDPM": "Nicotine-Free Dry Particulate Matter (NFDPM)",
        "CO": "Carbon Monoxide (CO)",
        "TAR": "Tar (TAR)",
        "NNN": "N-Nitrosonornicotine (NNN)",
        "NNK": "4-(Methylnitrosamino)-1-(3-pyridyl)-1-butanone (NNK)",
        
        # 측정 및 시험
        "ISO": "International Organization for Standardization (ISO)",
        "FTC": "Federal Trade Commission (FTC)",
        "HCI": "Health Canada Intense (HCI)",
        "CRM": "Certified Reference Material (CRM)",
        
        # 규제 용어
        "GRAS": "Generally Recognized as Safe (GRAS)",
        "GMP": "Good Manufacturing Practice (GMP)",
        "QC": "Quality Control (QC)",
        "SOP": "Standard Operating Procedure (SOP)"
    }
    
    # 정의 패턴 (미국 규제 전용)
    DEFINITION_PATTERNS = [
        r'["\']?([a-zA-Z\s]{3,30})["\']?\s+(?:means?|is\s+defined\s+as|shall\s+be)',
        r'(?:the\s+term\s+)?["\']?([a-zA-Z\s]{3,30})["\']?\s+(?:means?|includes?)',
        r'"([^"]{3,30})"\s+(?:means?|refers\s+to)',
    ]
    
    # 약어 패턴 (강화)
    ACRONYM_PATTERNS = [
        r'\b([A-Z]{2,6})\s*\(([^)]{5,50})\)',  # FDA (Food and Drug Administration)
        r'\(([A-Z]{2,6})\)\s*([^.]{5,50})',   # (FDA) Food and Drug Administration
        r'([A-Z]{2,6})\s*[–—-]\s*([^.]{5,50})',  # FDA – Food and Drug Administration
    ]
    
    def __init__(self, use_domain_dict: bool = True):
        """
        초기화 (청킹 통합용).
        
        Args:
            use_domain_dict: 도메인 특화 용어 사전 사용 여부
        """
        self.use_domain_dict = use_domain_dict
        logger.info(f"✅ DefinitionExtractor 초기화: domain_dict={use_domain_dict}")
    
    def extract_definitions_and_acronyms(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 정의와 약어를 추출 (청킹용).
        
        Returns:
            Dict[str, Any]: {
                "definitions": [{"term": str, "definition": str, "position": int}, ...],
                "acronyms": [{"acronym": str, "full_form": str, "position": int}, ...]
            }
        """
        return {
            "definitions": self._extract_term_definitions(text),
            "acronyms": self._extract_acronyms(text)
        }
    
    def _extract_term_definitions(self, text: str) -> List[Dict[str, Any]]:
        """용어 정의 추출 (청킹용)."""
        definitions = []
        seen_terms = set()
        
        for pattern in self.DEFINITION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                term = match.group(1).strip()
                
                if not term or len(term) < 3 or len(term) > 30 or term.lower() in seen_terms:
                    continue
                
                # 정의 문장 추출 (간단하게)
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 100)
                definition = text[start:end].strip()
                
                definitions.append({
                    "term": term,
                    "definition": definition,
                    "position": match.start()
                })
                
                seen_terms.add(term.lower())
        
        return definitions[:10]  # 최대 10개
    
    def _extract_acronyms(self, text: str) -> List[Dict[str, Any]]:
        """약어 추출 (청킹용)."""
        acronyms = []
        seen_acronyms = set()
        
        for pattern in self.ACRONYM_PATTERNS:
            for match in re.finditer(pattern, text):
                acronym = match.group(1).strip()
                full_form = match.group(2).strip()
                
                if acronym in seen_acronyms or len(acronym) < 2:
                    continue
                
                acronyms.append({
                    "acronym": acronym,
                    "full_form": full_form,
                    "position": match.start()
                })
                
                seen_acronyms.add(acronym)
        
        return acronyms[:5]  # 최대 5개
    
    def has_definition_in_range(self, text: str, start: int, end: int) -> bool:
        """
        특정 범위에 정의가 있는지 확인 (청킹용).
        
        Args:
            text: 전체 텍스트
            start: 시작 위치
            end: 끝 위치
        
        Returns:
            bool: 정의 존재 여부
        """
        chunk_text = text[start:end]
        for pattern in self.DEFINITION_PATTERNS:
            if re.search(pattern, chunk_text, re.IGNORECASE):
                return True
        return False
    
    def normalize_tobacco_terms(self, text: str) -> str:
        """
        담배 규제 도메인 특화 용어 정규화.
        
        Args:
            text: 원본 텍스트
            
        Returns:
            str: 정규화된 텍스트 (약어 → 풀네임 확장)
        """
        if not self.use_domain_dict or not text:
            return text
            
        normalized_text = text
        
        # 도메인 사전 적용
        for abbr, full_form in self.TOBACCO_TERMS_DICT.items():
            # 이미 확장된 형태가 아닌 경우에만 치환
            if abbr in normalized_text and full_form not in normalized_text:
                # 단어 경계 확인하여 정확한 매칭
                pattern = r'\b' + re.escape(abbr) + r'\b'
                normalized_text = re.sub(pattern, full_form, normalized_text)
                
        return normalized_text
    
    def extract_domain_specific_terms(self, text: str) -> List[Dict[str, str]]:
        """
        텍스트에서 도메인 특화 용어 추출.
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            List[Dict]: 발견된 용어 리스트
        """
        found_terms = []
        
        for abbr, full_form in self.TOBACCO_TERMS_DICT.items():
            # 약어가 텍스트에 있는지 확인
            pattern = r'\b' + re.escape(abbr) + r'\b'
            matches = list(re.finditer(pattern, text))
            
            if matches:
                found_terms.append({
                    "term": abbr,
                    "full_form": full_form,
                    "count": len(matches),
                    "positions": [m.start() for m in matches]
                })
                
        return found_terms
    
    def get_term_definition(self, term: str) -> Optional[str]:
        """
        특정 용어의 정의 반환.
        
        Args:
            term: 조회할 용어
            
        Returns:
            Optional[str]: 용어 정의 (없으면 None)
        """
        return self.TOBACCO_TERMS_DICT.get(term.upper())
    
    def add_custom_term(self, abbr: str, full_form: str) -> None:
        """
        사용자 정의 용어 추가.
        
        Args:
            abbr: 약어
            full_form: 풀네임
        """
        self.TOBACCO_TERMS_DICT[abbr.upper()] = full_form
        logger.debug(f"사용자 정의 용어 추가: {abbr} → {full_form}")
    
    def get_all_terms(self) -> Dict[str, str]:
        """
        모든 도메인 용어 사전 반환.
        
        Returns:
            Dict[str, str]: 전체 용어 사전
        """
        return self.TOBACCO_TERMS_DICT.copy()