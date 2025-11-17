"""
module: definition_extractor_v2.py
description: 규제 문서에서 용어, 정의, 약자, 계층 구조 추출 (도메인 특화)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - re, logging, json
"""

import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class DefinitionExtractor:
    """
    규제 문서에서 정의/용어/약자/계층 구조를 추출합니다.
    
    주요 기능:
    1. 용어 정의 자동 감지 (미국: "As used in", "the term", 한국: "라는", "이란")
    2. 약자 감지 및 정규화 (FDA, CFR, BPC 등)
    3. 계층 구조 추출 (장→절→조→항 or Division→Chapter→Section)
    4. 교차 참조 링크 생성
    """
    
    # ==================== 정의 패턴 ====================
    DEFINITION_PATTERNS = [
        r'(?:as\s+used\s+in\s+)?(?:the\s+)?["\']?([a-zA-Z_][a-zA-Z0-9\s_-]*?)["\']?\s+(?:means?|is|shall\s+be|includes?)',
        r'["\']([a-zA-Z_][a-zA-Z0-9\s_-]*?)["\']\s+shall\s+(?:be\s+)?(?:defined\s+)?as',
        r'definition(?:s)?:?\s+["\']?([a-zA-Z_][a-zA-Z0-9\s_-]*?)["\']?\s+(?:means?|is)',
    ]
    
    # ==================== 약자 패턴 ====================
    ACRONYM_PATTERNS = [
        # "FDA (Food and Drug Administration)" 형식
        r'\b([A-Z]{2,})\s*\(\s*([^)]{5,100}?)\s*\)',
        # "FDA, the Food and Drug Administration" 형식
        r'\b([A-Z]{2,})\s*,\s*(?:the\s+)?([a-zA-Z\s]{5,100})',
    ]
    
    # ==================== 미국 계층 구조 패턴 ====================
    US_HIERARCHY_PATTERNS = {
        "division": r'(?:division|div\.?)\s+(\d+[.,]?\d*)',  # Division 8.6
        "chapter": r'(?:chapter|ch\.?)\s+(\d+)',  # Chapter 3
        "section": r'(?:section|sec\.?|§)\s+(\d+)',  # Section 22975
        "subsection": r'(?:\(\s*[a-z]\s*\)|subsection)',  # (a), (b)
    }
    
    # ==================== 참조 패턴 ====================
    REFERENCE_PATTERNS = [
        r'(?:see|section\s+\d+)',
    ]
    
    def __init__(self):
        """초기화."""
        logger.info("✅ DefinitionExtractor v2 initialized")
    
    def extract_definitions(
        self,
        document_text: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        문서에서 정의/용어를 추출합니다.
        
        Args:
            document_text: 규제 문서 텍스트
            country: 국가 코드 (KR, US 등) - 패턴 최적화용
        
        Returns:
            Dict with:
            {
                "definitions": [
                    {"term": "담배", "definition": "...", "confidence": 0.95},
                    ...
                ],
                "acronyms": [
                    {"acronym": "FDA", "full_form": "Food and Drug Administration", "confidence": 1.0},
                    ...
                ],
                "hierarchy": {
                    "type": "korean" | "american",
                    "structure": [...],
                },
                "references": [
                    {"source": "제1조", "target": "제2조", "type": "cross_reference"},
                    ...
                ],
            }
        """
        return {
            "definitions": self._extract_term_definitions(document_text),
            "acronyms": self._extract_acronyms(document_text),
            "hierarchy": self._extract_hierarchy(document_text, country),
            "references": self._extract_references(document_text),
        }
    
    # ==================== 정의 추출 ====================
    
    def _extract_term_definitions(self, text: str) -> List[Dict[str, Any]]:
        """용어 정의 추출."""
        definitions = []
        seen_terms = set()
        
        for pattern in self.DEFINITION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                term = match.group(1).strip() if match.lastindex >= 1 else None
                
                if not term or len(term) < 2 or len(term) > 100:
                    continue
                
                if term.lower() in seen_terms:
                    continue
                
                # 앞뒤 맥락 추출 (200자)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 150)
                context = text[start:end].strip()
                
                definitions.append({
                    "term": term,
                    "definition": context,
                    "confidence": self._calculate_definition_confidence(context),
                })
                
                seen_terms.add(term.lower())
        
        logger.debug(f"✅ Found {len(definitions)} term definitions")
        return definitions[:50]  # 최대 50개
    
    def _calculate_definition_confidence(self, context: str) -> float:
        """정의의 신뢰도 계산."""
        score = 0.5  # 기본점
        
        # 명시적 정의 표현
        if re.search(r'(?:means?|is|shall\s+be|defined|라는|이란)', context, re.IGNORECASE):
            score += 0.3
        
        # 길이 (너무 짧거나 길면 낮은 신뢰도)
        if 20 < len(context) < 300:
            score += 0.2
        
        return min(score, 1.0)
    
    # ==================== 약자 추출 ====================
    
    def _extract_acronyms(self, text: str) -> List[Dict[str, Any]]:
        """약자 및 약자 정의 추출."""
        acronyms = []
        seen_acronyms = set()
        
        for pattern in self.ACRONYM_PATTERNS:
            matches = re.finditer(pattern, text)
            
            for match in matches:
                acronym = match.group(1).strip()
                full_form = match.group(2).strip()
                
                if acronym in seen_acronyms or len(acronym) < 2:
                    continue
                
                acronyms.append({
                    "acronym": acronym,
                    "full_form": full_form,
                    "confidence": 1.0 if len(full_form) > 5 else 0.7,
                })
                
                seen_acronyms.add(acronym)
        
        logger.debug(f"✅ Found {len(acronyms)} acronyms")
        return acronyms[:30]  # 최대 30개
    
    # ==================== 계층 구조 추출 ====================
    
    def _extract_hierarchy(
        self,
        text: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """문서 계층 구조 추출 (미국 규제 전용)."""
        return self._extract_american_hierarchy(text)
    
    def _extract_american_hierarchy(self, text: str) -> Dict[str, Any]:
        """미국식 계층 구조 추출 (Division→Chapter→Section)."""
        structure = []
        current_division = None
        current_chapter = None
        
        # Division 추출
        for match in re.finditer(self.US_HIERARCHY_PATTERNS["division"], text):
            division_num = match.group(1)
            
            current_division = {
                "level": "Division",
                "number": division_num,
                "title": self._extract_section_title(text, match.end(), "Chapter"),
                "children": [],
            }
            structure.append(current_division)
            current_chapter = None
        
        # Chapter 추출
        for match in re.finditer(self.US_HIERARCHY_PATTERNS["chapter"], text):
            chapter_num = match.group(1)
            
            current_chapter = {
                "level": "Chapter",
                "number": chapter_num,
                "title": self._extract_section_title(text, match.end(), "Section"),
                "children": [],
            }
            
            if current_division:
                current_division["children"].append(current_chapter)
            else:
                structure.append(current_chapter)
        
        # Section 추출
        for match in re.finditer(self.US_HIERARCHY_PATTERNS["section"], text):
            section_num = match.group(1)
            section_text = self._extract_section_title(text, match.end(), None)
            
            section_obj = {
                "level": "Section",
                "number": section_num,
                "title": section_text,
            }
            
            if current_chapter:
                current_chapter["children"].append(section_obj)
            elif current_division:
                current_division["children"].append(section_obj)
            else:
                structure.append(section_obj)
        
        return {
            "type": "american",
            "structure": structure,
            "total_divisions": len([s for s in structure if s.get("level") == "Division"]),
            "total_chapters": sum(
                len(c.get("children", [])) for c in structure 
                if c.get("level") == "Division"
            ),
        }
    
    def _extract_section_title(
        self,
        text: str,
        start_pos: int,
        end_marker: Optional[str] = None,
        max_chars: int = 100
    ) -> str:
        """섹션 제목 추출."""
        end_pos = min(start_pos + max_chars, len(text))
        
        if end_marker:
            marker_pos = text.find(end_marker, start_pos)
            if marker_pos != -1:
                end_pos = marker_pos
        
        title = text[start_pos:end_pos].strip()
        # 첫 줄만 사용
        title = title.split("\n")[0]
        
        return title[:100]  # 최대 100자
    
    # ==================== 교차 참조 추출 ====================
    
    def _extract_references(self, text: str) -> List[Dict[str, str]]:
        """문서 내 교차 참조 추출."""
        references = []
        
        # 미국식 참조 (Section X)
        us_ref_pattern = r'(?:section|sec\.?|§)\s+(\d+)'
        for match in re.finditer(us_ref_pattern, text, re.IGNORECASE):
            section = match.group(1)
            
            references.append({
                "source": f"Section {section}",
                "target": f"Section {section}",
                "type": "cross_reference",
            })
        
        logger.debug(f"✅ Found {len(references)} cross references")
        return list({json.dumps(r, sort_keys=True): r for r in references}.values())[:30]
    
    def batch_extract_definitions(
        self,
        documents: List[Dict[str, str]],
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """여러 문서에서 정의를 배치 추출합니다."""
        results = []
        total = len(documents)
        
        for i, doc in enumerate(documents, 1):
            try:
                definitions = self.extract_definitions(
                    document_text=doc.get("text", ""),
                    country=doc.get("country")
                )
                results.append(definitions)
                
                if show_progress:
                    logger.info(
                        f"[{i}/{total}] ✅ Extracted: "
                        f"definitions={len(definitions['definitions'])}, "
                        f"acronyms={len(definitions['acronyms'])}"
                    )
            
            except Exception as e:
                logger.error(f"[{i}/{total}] ❌ Error: {str(e)}")
                results.append({"error": str(e)})
        
        logger.info(f"✅ Batch extraction complete: {total} documents processed")
        return results



