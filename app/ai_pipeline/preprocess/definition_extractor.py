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
    """
    
    # 정의 패턴 (미국 규제 전용)
    DEFINITION_PATTERNS = [
        r'["\'']?([a-zA-Z\s]{3,30})["\'']?\s+(?:means?|is\s+defined\s+as|shall\s+be)',
        r'(?:the\s+term\s+)?["\'']?([a-zA-Z\s]{3,30})["\'']?\s+(?:means?|includes?)',
    ]
    
    # 약어 패턴 (간소화)
    ACRONYM_PATTERNS = [
        r'\b([A-Z]{2,6})\s*\(([^)]{5,50})\)',  # FDA (Food and Drug Administration)
    ]
    
    def __init__(self):
        """초기화 (청킹 통합용)."""
        logger.info("✅ DefinitionExtractor 초기화 (미국 규제 전용)")
    
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