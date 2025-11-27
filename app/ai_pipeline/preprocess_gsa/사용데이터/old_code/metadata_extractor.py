"""
module: metadata_extractor_v2.py
description: 규제 문서의 메타데이터 추출 (도메인 특화 - 담배 규제 + 한국 법령)
             미국 담배 규제(연방/주/지방법) + 한국 법령 자동 감지
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - re, json, logging, datetime, pathlib
"""

from typing import Optional, Dict, Any, List, Tuple, Union
import re
import json
import logging
from datetime import datetime
from pathlib import Path

# LangChain imports (optional)
try:
    from langchain_community.document_loaders import (
        PyPDFLoader, 
        TextLoader, 
        UnstructuredPDFLoader,
        UnstructuredWordDocumentLoader
    )
    from langchain.schema import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # 폴백용 더미 클래스
    class Document:
        def __init__(self, page_content="", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

logger = logging.getLogger(__name__)

if not LANGCHAIN_AVAILABLE:
    logger.warning("LangChain not available. Using pattern-based extraction only.")


class RegulationPatterns:
    """규제 문서 패턴 집합 (도메인: 담배 규제 + 한국 법령)"""
    
    # ==================== 담배 관련 키워드 ====================
    TOBACCO_KEYWORDS = {
        "tobacco", "cigarette", "smoking", "nicotine", "vape", "e-cigarette",
        "cigar", "pipe", "smokeless", "snuff", "chewing", "tobacco product",
        "담배", "흡연", "담배제품", "니코틴", "궐련", "육연", "씹는담배",
    }
    
    # ==================== 미국 관할권 패턴 ====================
    FEDERAL_INDICATORS = [
        r"(?:public\s+)?law\s+\d+[-–]\d+",  # Public Law 111-31
        r"congress(?:ional)?\b",
        r"(?:united\s+)?states\s+code\s*\(?\d+\s*(?:u\.?s\.?c\.?|usc)\)?",  # 15 USC
        r"\bstat\.\s+\d+",  # 123 STAT. 1776
        r"(?:senate|house)\s+bill",
        r"h\.?r\.?\s+\d+|s\.?\s+\d+",  # HR 1256, S 100
        r"federal\s+(?:statute|law|regulation|register)",
        r"(?:title\s+)?21\s+(?:cfr|code\s+of\s+federal\s+regulations)",
    ]
    
    STATE_INDICATORS = [
        r"(?:division|part|chapter|section|article)\s+\d+[.,]?\s*\d*",  # Division 8.6
        r"(?:california|florida|texas|new\s+york|pennsylvania|ohio|illinois)\b",
        r"(?:california\s+)?(?:business\s+[&and]\s+)?profession",
        r"state\s+(?:board|law|code|statute)",
        r"(?:bpc|california\s+business\s+and\s+professions\s+code)",
        r"\bca\s+(?:code|statute)",
    ]
    
    LOCAL_INDICATORS = [
        r"(?:san\s+francisco|los\s+angeles|new\s+york\s+city|chicago|seattle)",
        r"(?:city|county|municipal|township|ordinance)",
        r"(?:ordinance|municipal\s+code)\s+(?:no\.?|#|\d+)",
        r"health\s+(?:code|department|ordinance)",
    ]
    
    # ==================== 규제기관 패턴 ====================
    REGULATORY_BODY_MAP = {
        "FDA": [
            r"(?:food\s+and\s+drug\s+administration|fda)",
            r"center\s+for\s+tobacco\s+products",
            r"ctp\b",
            r"(?:title\s+)?21\s+cfr",
        ],
        "State Board": [
            r"state\s+board(?:\s+of)?",
            r"board\s+of\s+(?:equalization|revenue|supervisors)",
            r"state\s+(?:health|revenue|regulatory|licensing)\s+(?:department|board)",
        ],
        "Local Health Dept": [
            r"(?:city|county|municipal|local)\s+(?:health|department)",
            r"health\s+(?:and\s+)?(?:safety|services|code)",
            r"department\s+of\s+(?:public\s+)?health",
        ],
    }
    
    # ==================== 법의 유형 패턴 ====================
    LAW_TYPE_MAP = {
        "statute": [
            r"(?:public\s+)?law\s+\d+[–-]\d+",
            r"statute\s+\d+",
            r"act(?:\s+of)?\s+\d{4}",
            r"법\s+(?:제\s*)?\d+호",  # 한국: 법 XX호
        ],
        "code": [
            r"(?:\d+\s+)?(?:u\.?s\.?c\.?|usc)",  # 15 USC
            r"(?:california\s+)?(?:penal|health|business|professional|revenue|government)\s+code",
            r"california\s+business\s+and\s+professions\s+code",
            r"(?:bpc|code)\s+(?:section|§)",
        ],
        "regulation": [
            r"(?:federal\s+)?regulation",
            r"(?:title\s+)?21\s+cfr",
            r"code\s+of\s+federal\s+regulations",
            r"(?:state\s+)?regulation",
            r"시행령|시행규칙",  # 한국
        ],
        "rule": [
            r"(?:proposed\s+)?rule(?:\s+\(cfr\))?",
            r"final\s+rule",
            r"규정|규칙",  # 한국
        ],
        "notice": [
            r"(?:federal\s+)?register",
            r"notice(?:\s+of)?",
            r"proposed\s+(?:amendment|regulation|rule)",
            r"공고|고시",  # 한국
        ],
    }
    
    # ==================== 날짜 패턴 ====================
    DATE_FORMATS = [
        (r"(\d{4})[년-](\d{1,2})[월-](\d{1,2})[일]?", "YMD_KO"),  # 2025년1월12일
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "YMD"),  # 2025-01-12
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "DMY"),  # 12/01/2025
        (r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s+(\d{4})",
         "MDA"),  # January 12, 2025
    ]


class MetadataExtractor:
    """
    규제 문서 메타데이터 추출기 (v2: 도메인 특화).
    
    주요 기능:
    1. 자동 관할권 감지 (federal/state/local/national)
    2. 자동 규제기관 감지 (FDA, State Board, Local Health Dept)
    3. 자동 법의 유형 분류 (statute/code/regulation/rule/notice)
    4. 담배 규제 전문 메타데이터 추출
    5. 한국 법령 형식 지원
    
    추출 메타데이터:
    - title: 문서 제목
    - country: 국가 코드 (KR, US)
    - jurisdiction: 관할권 (federal/state/local/national)
    - regulatory_body: 규제기관 (FDA/State Board/Local Health Dept)
    - law_type: 법의 유형 (statute/code/regulation/rule/notice)
    - regulation_type: 규제 카테고리 (tobacco_control/healthcare/etc)
    - publication_date: 발표 날짜
    - effective_date: 발효 날짜
    - keywords: 키워드 (담배, nicotine 등)
    - confidence: 추출 신뢰도 (0.0~1.0)
    """
    
    def __init__(self, use_langchain: bool = True):
        """초기화.
        
        Args:
            use_langchain: LangChain DocumentLoader 사용 여부
        """
        self.patterns = RegulationPatterns()
        self.use_langchain = use_langchain and LANGCHAIN_AVAILABLE
        
        if self.use_langchain:
            logger.info("✅ MetadataExtractor v2 initialized (LangChain + Pattern-based)")
        else:
            logger.info("✅ MetadataExtractor v2 initialized (Pattern-based only)")
    
    def extract_metadata(
        self,
        document_text: str,
        filename: Optional[str] = None,
        source_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        문서에서 메타데이터를 추출합니다.
        
        Args:
            document_text: 규제 문서 텍스트
            filename: 원본 파일명 (관할권 감지에 활용)
            source_url: 출처 URL
        
        Returns:
            Dict[str, Any]: 추출된 메타데이터
            {
                "title": str,
                "country": str ("KR", "US", etc),
                "jurisdiction": str ("federal", "state", "local", "national"),
                "regulatory_body": str ("FDA", "State Board", "Local Health Dept"),
                "law_type": str ("statute", "code", "regulation", "rule", "notice"),
                "regulation_type": str ("tobacco_control"),
                "publication_date": str (ISO format),
                "effective_date": Optional[str],
                "keywords": List[str],
                "summary": str (첫 300자),
                "confidence": float (0.0~1.0),
                "source_url": Optional[str],
                "filename": Optional[str],
                "extracted_at": str (ISO format),
            }
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty")
        
        # 기본 추출
        metadata = {
            "title": self._extract_title(document_text),
            "country": self._extract_country(document_text, filename),
            "jurisdiction": self._extract_jurisdiction(document_text, filename),
            "regulatory_body": self._extract_regulatory_body(document_text),
            "law_type": self._extract_law_type(document_text),
            "regulation_type": self._extract_regulation_type(document_text),
            "publication_date": self._extract_publication_date(document_text),
            "effective_date": self._extract_effective_date(document_text),
            "keywords": self._extract_keywords(document_text),
            "summary": self._extract_summary(document_text),
            "source_url": source_url,
            "filename": filename,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "legal_hierarchy": self._extract_legal_hierarchy(document_text),
            "external_id": self._extract_external_id(filename or ""),
            "document_hash": self._calculate_document_hash(document_text),
        }
        
        # 신뢰도 점수 계산
        metadata["confidence"] = self._calculate_confidence(metadata)
        
        logger.info(
            f"✅ Metadata extracted: title={metadata['title'][:50]}... "
            f"country={metadata['country']}, jurisdiction={metadata['jurisdiction']}, "
            f"confidence={metadata['confidence']:.2f}"
        )
        
        return metadata
    
    # ==================== 추출 메서드 ====================
    
    def _extract_title(self, text: str) -> str:
        """제목 추출 (UI 텍스트 필터링 개선)."""
        lines = text.strip().split("\n")
        
        # UI/웹페이지 텍스트 패턴 (제외할 것들)
        ui_patterns = [
            r"^(?:code|select|search|section|up|add|to|my|favorites)\s*:?",
            r"^[\d\s\|\-\+\=]+$",  # 숫자/기호만
            r"^\s*[\"\']?case_id[\"\']?\s*:",  # JSON 키
            r"^\s*\{|^\s*\[",  # JSON 시작
        ]
        
        for line in lines[:15]:  # 더 많은 줄 검사
            line = line.strip()
            
            # 기본 필터
            if not line or len(line) < 5 or len(line) > 500:
                continue
            
            # UI 패턴 제외
            if any(re.search(p, line, re.IGNORECASE) for p in ui_patterns):
                continue
            
            # 숫자/기호만 있는 줄 제외
            if not re.search(r"[가-힣a-zA-Z]", line):
                continue
            
            # 법률 제목 패턴 우선 (더 정확한 제목)
            if re.search(r"(?:public\s+law|act|법률|규정|고시)", line, re.IGNORECASE):
                return line
            
            # 일반적인 제목 길이 체크
            if 15 < len(line) < 200:  # 범위 조정
                return line
        
        return "제목 미확인"
    
    def _extract_country(self, text: str, filename: Optional[str]) -> str:
        """국가 코드 추출 (미국 규제 전용)."""
        text_lower = text.lower()
        
        # 미국 지표 (점수 시스템)
        us_score = sum([
            2 if re.search(r"united\s+states", text_lower) else 0,
            2 if re.search(r"congress", text_lower) else 0,
            2 if re.search(r"public\s+law\s+\d+[-–]\d+", text_lower) else 0,
            1 if re.search(r"\d+\s+u\.?s\.?c\.?", text_lower) else 0,
            1 if re.search(r"california|florida|texas|new\s+york", text_lower) else 0,
        ])
        
        # 파일명 보조 점수
        if filename:
            filename_lower = filename.lower()
            if "fda" in filename_lower or "congress" in filename_lower:
                us_score += 1
        
        return "US" if us_score >= 2 else "UNKNOWN"
    
    def _extract_jurisdiction(self, text: str, filename: Optional[str]) -> str:
        """관할권 추출 (개선된 우선순위)."""
        text_lower = text.lower()
        
        # Local 확인 (우선순위 높임 - 구체적 패턴)
        local_strong_patterns = [
            r"san\s+francisco", r"los\s+angeles", r"new\s+york\s+city",
            r"municipal\s+code", r"city\s+ordinance", r"county\s+health"
        ]
        if any(re.search(p, text_lower) for p in local_strong_patterns):
            return "local"
        
        # Federal 확인 (강한 지표)
        federal_strong_patterns = [
            r"public\s+law\s+\d+[-–]\d+", r"congress(?:ional)?",
            r"federal\s+register", r"\d+\s+u\.?s\.?c\.?"
        ]
        if any(re.search(p, text_lower) for p in federal_strong_patterns):
            return "federal"
        
        # State 확인
        if any(re.search(p, text_lower) for p in self.patterns.STATE_INDICATORS):
            return "state"
        
        # 약한 Federal 패턴 (마지막 체크)
        if any(re.search(p, text_lower) for p in self.patterns.FEDERAL_INDICATORS):
            return "federal"
        
        return "unknown"
    
    def _extract_regulatory_body(self, text: str) -> Optional[str]:
        """규제기관 추출 (우선순위 수정으로 오매칭 방지)."""
        text_lower = text.lower()
        
        # FDA 우선 확인 (가장 구체적)
        fda_patterns = self.patterns.REGULATORY_BODY_MAP["FDA"]
        if any(re.search(p, text_lower) for p in fda_patterns):
            return "FDA"
        
        # State Board 확인
        state_patterns = self.patterns.REGULATORY_BODY_MAP["State Board"]
        if any(re.search(p, text_lower) for p in state_patterns):
            return "State Board"
        
        # Local Health Dept 확인 (마지막, 가장 일반적)
        local_patterns = self.patterns.REGULATORY_BODY_MAP["Local Health Dept"]
        if any(re.search(p, text_lower) for p in local_patterns):
            # 연방법 문서에서는 Local Health Dept 제외
            if re.search(r"public\s+law|congress|federal\s+register", text_lower):
                return None
            return "Local Health Dept"
        
        return None
    
    def _extract_law_type(self, text: str) -> str:
        """법의 유형 추출."""
        text_lower = text.lower()
        
        for law_type, patterns in self.patterns.LAW_TYPE_MAP.items():
            if any(re.search(p, text_lower) for p in patterns):
                return law_type
        
        return "regulation"  # 기본값
    
    def _extract_regulation_type(self, text: str) -> str:
        """규제 카테고리 추출."""
        text_lower = text.lower()
        
        # 담배 관련 여부 확인
        if any(keyword in text_lower for keyword in self.patterns.TOBACCO_KEYWORDS):
            return "tobacco_control"
        
        # 다른 카테고리
        if any(keyword in text_lower for keyword in ["healthcare", "medical", "device"]):
            return "healthcare"
        if any(keyword in text_lower for keyword in ["food", "safety"]):
            return "food_safety"
        if any(keyword in text_lower for keyword in ["environmental", "pollution"]):
            return "environment"
        
        return "general"
    
    def _extract_publication_date(self, text: str) -> Optional[str]:
        """발표 날짜 추출."""
        # 특정 패턴 검색
        patterns = [
            r"(?:published|issued|enacted|공포|발표)(?:\s+on)?\s*[:\s]*([^\n]+)",
            r"(?:public\s+law\s+\d+[-–]\d+|bill\s+no\.?\s*\d+)?.*?(\d{4})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = self._normalize_date(match.group(1))
                if date_str:
                    return date_str
        
        # 문서 첫 부분에서 첫 번째 날짜 추출
        first_match = re.search(r"(\d{4})[년-](\d{1,2})[월-](\d{1,2})|(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
        if first_match:
            return self._normalize_date(first_match.group(0))
        
        return None
    
    def _extract_effective_date(self, text: str) -> Optional[str]:
        """발효 날짜 추출."""
        patterns = [
            r"(?:effective|시행|발효)(?:\s+on)?\s*[:\s]*([^\n]+)",
            r"(?:effective\s+date|시행일)\s*[:\s]*(\d{4}[/-]?\d{1,2}[/-]?\d{1,2})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = self._normalize_date(match.group(1))
                if date_str:
                    return date_str
        
        return None
    
    def _extract_keywords(self, text: str) -> List[str]:
        """키워드 추출."""
        keywords = []
        text_lower = text.lower()
        
        # 담배 관련 키워드 확인
        tobacco_keywords = [kw for kw in self.patterns.TOBACCO_KEYWORDS 
                           if kw in text_lower]
        keywords.extend(tobacco_keywords[:5])  # 최대 5개
        
        # 추가 도메인 키워드
        additional_keywords = {
            "warning": r"warning|경고|주의",
            "label": r"label|라벨|표시",
            "manufacturing": r"manufactur|제조",
            "distribution": r"distribut|배포",
            "advertising": r"advertis|광고",
            "prohibition": r"prohibit|금지",
        }
        
        for kw, pattern in additional_keywords.items():
            if re.search(pattern, text_lower):
                keywords.append(kw)
        
        return list(set(keywords))[:10]  # 중복 제거, 최대 10개
    
    def _extract_summary(self, text: str, max_length: int = 300) -> str:
        """요약 추출 (첫 N자)."""
        cleaned = re.sub(r"[\s]+", " ", text.strip())
        return cleaned[:max_length] + ("..." if len(cleaned) > max_length else "")
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """날짜 문자열을 ISO 형식으로 정규화 (개선된 검증)."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # 한국 형식: 2025년1월12일 → 2025-01-12
        match = re.match(r"(\d{4})[년-](\d{1,2})[월-](\d{1,2})[일]?", date_str)
        if match:
            year, month, day = match.groups()
            if self._is_valid_date(int(year), int(month), int(day)):
                return f"{year}-{int(month):02d}-{int(day):02d}"
        
        # 표준 형식: 2025-01-12 or 2025/01/12
        match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_str)
        if match:
            year, month, day = match.groups()
            if self._is_valid_date(int(year), int(month), int(day)):
                return f"{year}-{int(month):02d}-{int(day):02d}"
        
        # 영문 월: January 12, 2025
        match = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2}),?\s+(\d{4})", 
                         date_str, re.IGNORECASE)
        if match:
            month_str, day, year = match.groups()
            months = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            }
            month_num = months.get(month_str[:3].lower(), 1)
            if self._is_valid_date(int(year), month_num, int(day)):
                return f"{year}-{month_num:02d}-{int(day):02d}"
        
        return None
    
    def _is_valid_date(self, year: int, month: int, day: int) -> bool:
        """날짜 유효성 검증."""
        if year < 1900 or year > 2100:
            return False
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        # 간단한 월별 일수 체크
        days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return day <= days_in_month[month - 1]
    

    
    def _extract_legal_hierarchy(self, text: str) -> Optional[Dict[str, str]]:
        """법률 계층 메타데이터 추출 (개선된 패턴 매칭)."""
        hierarchy = {}
        
        # CFR 우선 확인: 21 CFR § 1160.10
        cfr_match = re.search(r'(\d+)\s+CFR\s+(?:Part\s+)?(\d+)(?:\.(\d+))?', text, re.IGNORECASE)
        if cfr_match:
            hierarchy['regulation_type'] = 'CFR'
            hierarchy['title'] = cfr_match.group(1)
            hierarchy['part'] = cfr_match.group(2)
            if cfr_match.group(3):
                hierarchy['section'] = f"{cfr_match.group(2)}.{cfr_match.group(3)}"
                hierarchy['full_citation'] = f"{cfr_match.group(1)} CFR § {cfr_match.group(2)}.{cfr_match.group(3)}"
            else:
                hierarchy['section'] = cfr_match.group(2)
                hierarchy['full_citation'] = f"{cfr_match.group(1)} CFR Part {cfr_match.group(2)}"
            return hierarchy
        
        # USC 확인: 21 U.S.C. § 387
        usc_match = re.search(r'(\d+)\s+U\.?S\.?C\.?\s+§?\s*(\d+)', text, re.IGNORECASE)
        if usc_match:
            hierarchy['regulation_type'] = 'USC'
            hierarchy['title'] = usc_match.group(1)
            hierarchy['section'] = usc_match.group(2)
            hierarchy['full_citation'] = f"{usc_match.group(1)} U.S.C. § {usc_match.group(2)}"
            return hierarchy
        
        # Public Law 확인: Public Law 111-31
        publaw_match = re.search(r'public\s+law\s+(\d+)[-–](\d+)', text, re.IGNORECASE)
        if publaw_match:
            hierarchy['regulation_type'] = 'Public Law'
            hierarchy['congress'] = publaw_match.group(1)
            hierarchy['law_number'] = publaw_match.group(2)
            hierarchy['full_citation'] = f"Public Law {publaw_match.group(1)}-{publaw_match.group(2)}"
            return hierarchy
        
        # State Code 확인: California Business and Professions Code Section 22975
        state_match = re.search(r'(california|florida|texas|new\s+york).*?(?:code|law).*?section\s+(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if state_match:
            hierarchy['regulation_type'] = 'State Law'
            hierarchy['state'] = state_match.group(1).title()
            hierarchy['section'] = state_match.group(2)
            return hierarchy
        
        return None
    
    def _extract_external_id(self, filename: str) -> Optional[str]:
        """외부 문서 ID 추출 (예: 2025-00397)."""
        match = re.search(r'(\d{4})-(\d{5})', filename)
        return match.group(0) if match else None
    
    def _calculate_document_hash(self, text: str) -> str:
        """문서 해시 계산 (SHA256)."""
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    def _calculate_confidence(self, metadata: Dict[str, Any]) -> float:
        """메타데이터 추출 신뢰도 계산 (0.0~1.0)."""
        score = 0.0
        max_score = 5.0
        
        # 제목이 확인되었는가?
        if metadata["title"] != "제목 미확인":
            score += 1.0
        
        # 국가가 확인되었는가?
        if metadata["country"] != "UNKNOWN":
            score += 1.0
        
        # 규제기관이 확인되었는가?
        if metadata["regulatory_body"]:
            score += 1.0
        
        # 발표 날짜가 확인되었는가?
        if metadata["publication_date"]:
            score += 1.0
        
        # 키워드가 확인되었는가?
        if metadata["keywords"]:
            score += 1.0
        
        return min(score / max_score, 1.0)
    
    # ==================== LangChain 통합 메서드 ====================
    
    def extract_from_file(
        self, 
        file_path: Union[str, Path], 
        use_langchain: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        파일에서 직접 메타데이터 추출 (LangChain + 패턴 기반 하이브리드).
        
        Args:
            file_path: 파일 경로
            use_langchain: LangChain 사용 여부 (None이면 인스턴스 설정 따름)
        
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        use_lc = use_langchain if use_langchain is not None else self.use_langchain
        
        if use_lc and LANGCHAIN_AVAILABLE:
            return self._extract_with_langchain(file_path)
        else:
            return self._extract_with_existing_processor(file_path)
    
    def _extract_with_langchain(self, file_path: Path) -> Dict[str, Any]:
        """
        LangChain DocumentLoader 표준화 기반 메타데이터 추출.
        
        핵심 개선:
        1. Document 구조 표준화 (page_content + metadata)
        2. 도메인 메타데이터 자동 추가
        3. 메타데이터 전파 보장
        4. 기존 pdf_processor 활용
        """
        logger.info(f"🔍 DocumentLoader 표준화 추출: {file_path.name}")
        
        try:
            # 1. LangChain 로더로 Document 구조 생성
            loader = self._get_langchain_loader(file_path)
            documents = loader.load()
            
            if not documents:
                raise ValueError("No documents loaded")
            
            # 2. 도메인 메타데이터 표준화
            standardized_docs = self._standardize_documents(documents, file_path)
            
            # 3. 전체 텍스트 결합 (메타데이터 보존)
            full_text = "\n\n".join([doc.page_content for doc in standardized_docs])
            
            # 4. 패턴 기반 추출 + Document 메타데이터 결합
            pattern_metadata = self.extract_metadata(
                document_text=full_text,
                filename=file_path.name,
                source_url=standardized_docs[0].metadata.get('source')
            )
            
            # 5. Document 메타데이터와 패턴 메타데이터 통합
            final_metadata = self._merge_document_metadata(
                documents=standardized_docs,
                pattern_meta=pattern_metadata
            )
            
            logger.info(
                f"✅ 표준화 추출 완료: {len(documents)}페이지, "
                f"confidence={final_metadata['confidence']:.2f}"
            )
            
            return final_metadata
            
        except Exception as e:
            logger.error(f"❌ DocumentLoader 실패, 기존 processor 사용: {e}")
            return self._extract_with_existing_processor(file_path)
    
    def _get_langchain_loader(self, file_path: Path):
        """
        파일 확장자별 최적 LangChain 로더 선택.
        
        논리:
        - PDF: PyPDFLoader (구조 보존) vs UnstructuredPDFLoader (텍스트 품질)
        - DOCX: UnstructuredWordDocumentLoader
        - TXT: TextLoader
        - 기타: 텍스트로 처리
        """
        suffix = file_path.suffix.lower()
        
        if suffix == '.pdf':
            # PDF: 구조화된 추출 우선
            try:
                return UnstructuredPDFLoader(str(file_path))
            except:
                return PyPDFLoader(str(file_path))
        
        elif suffix in ['.docx', '.doc']:
            return UnstructuredWordDocumentLoader(str(file_path))
        
        elif suffix in ['.txt', '.md']:
            return TextLoader(str(file_path), encoding='utf-8')
        
        else:
            # 기타 파일: 텍스트로 시도
            logger.warning(f"Unknown file type: {suffix}, using TextLoader")
            return TextLoader(str(file_path), encoding='utf-8')
    
    def _extract_langchain_metadata(self, documents: List[Document]) -> Dict[str, Any]:
        """
        LangChain Document 객체에서 메타데이터 추출.
        
        LangChain의 장점:
        - 파일 시스템 메타데이터 (생성일, 수정일, 크기)
        - 문서 구조 정보 (페이지 수, 섹션)
        - 자동 언어 감지
        """
        if not documents:
            return {}
        
        primary_doc = documents[0]
        metadata = primary_doc.metadata.copy()
        
        # LangChain 기본 메타데이터 정규화
        langchain_meta = {
            'langchain_source': metadata.get('source'),
            'langchain_page_count': len(documents),
            'langchain_total_chars': sum(len(doc.page_content) for doc in documents),
            'langchain_avg_page_length': sum(len(doc.page_content) for doc in documents) // len(documents),
        }
        
        # 파일 시스템 메타데이터 (있으면)
        if 'file_path' in metadata:
            file_path = Path(metadata['file_path'])
            if file_path.exists():
                stat = file_path.stat()
                langchain_meta.update({
                    'file_size_bytes': stat.st_size,
                    'file_created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'file_modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        
        # PDF 특화 메타데이터
        if 'page' in metadata:
            langchain_meta['pdf_page_number'] = metadata['page']
        
        return langchain_meta
    
    def _merge_document_metadata(
        self,
        documents: List[Document],
        pattern_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Document 메타데이터와 패턴 기반 메타데이터 통합.
        
        핵심: Document 구조의 메타데이터를 최대한 활용하여
        Qdrant 저장 시 필터링/검색에 최적화된 메타데이터 생성
        """
        # 패턴 기반을 기본으로 시작
        merged = pattern_meta.copy()
        
        # Document 메타데이터 통합
        if documents:
            primary_doc = documents[0]
            doc_meta = primary_doc.metadata
            
            merged.update({
                'extraction_method': 'document_loader_standardized',
                'page_count': len(documents),
                'source_file': doc_meta.get('source_file'),
                
                # 도메인 메타데이터 우선 적용 (Document에서 자동 감지된 것)
                'jurisdiction': doc_meta.get('jurisdiction', merged.get('jurisdiction')),
                'agency': doc_meta.get('agency', merged.get('regulatory_body')),
                'regulation_type': doc_meta.get('regulation_type', merged.get('regulation_type')),
                
                # Qdrant 필터링용 메타데이터
                'meta_source_type': 'document_loader',
                'meta_page_count': len(documents),
                'meta_extraction_method': 'langchain_standardized',
            })
            
            # 제목 개선 (Document source 활용)
            if merged['title'] == '제목 미확인' and doc_meta.get('source_file'):
                source_name = Path(doc_meta['source_file']).stem
                if len(source_name) > 5:
                    merged['title'] = source_name.replace('_', ' ').title()
            
            # 신뢰도 재계산 (Document 구조 정보 반영)
            confidence_boost = 0.0
            if len(documents) > 1:
                confidence_boost += 0.1  # 다중 페이지
            if doc_meta.get('jurisdiction'):
                confidence_boost += 0.1  # 자동 감지된 관할권
            if doc_meta.get('agency'):
                confidence_boost += 0.1  # 자동 감지된 기관
            
            merged['confidence'] = min(merged['confidence'] + confidence_boost, 1.0)
        
        return merged
    
    def _extract_with_existing_processor(self, file_path: Path) -> Dict[str, Any]:
        """
        기존 pdf_processor.py 활용한 안정적 추출.
        """
        logger.info(f"📄 기존 processor 활용: {file_path.name}")
        
        try:
            if file_path.suffix.lower() == '.pdf':
                # 기존 PDFProcessor 활용
                from app.ai_pipeline.preprocess.pdf_processor import PDFProcessor
                
                processor = PDFProcessor()
                pdf_result = processor.load_and_extract(str(file_path))
                
                if pdf_result["status"] == "success":
                    text = pdf_result["full_text"]
                    
                    # 패턴 기반 메타데이터 추출
                    metadata = self.extract_metadata(
                        document_text=text,
                        filename=file_path.name
                    )
                    
                    # PDFProcessor 메타데이터 추가
                    metadata.update({
                        'extraction_method': 'existing_pdf_processor',
                        'pdf_metadata': pdf_result.get('metadata', {}),
                        'page_count': pdf_result.get('metadata', {}).get('num_pages', 0)
                    })
                    
                    return metadata
                else:
                    raise RuntimeError(f"PDF 처리 실패: {pdf_result.get('error')}")
            else:
                # 텍스트 파일
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                metadata = self.extract_metadata(
                    document_text=text,
                    filename=file_path.name
                )
                metadata['extraction_method'] = 'text_file'
                return metadata
                
        except Exception as e:
            logger.error(f"❌ 기존 processor 실패: {e}")
            raise
    
    def _standardize_documents(self, documents: List[Document], file_path: Path) -> List[Document]:
        """
        Document 구조 표준화 및 도메인 메타데이터 추가.
        
        핵심: 규제 도메인 특화 메타데이터를 로딩 직후 추가하여
        청킹/임베딩/검색 단계에서 메타데이터가 전파되도록 보장
        """
        standardized = []
        
        for idx, doc in enumerate(documents):
            # 기본 메타데이터 보강
            enhanced_metadata = doc.metadata.copy()
            enhanced_metadata.update({
                # 파일 정보
                'source_file': file_path.name,
                'source_path': str(file_path),
                'page_number': enhanced_metadata.get('page', idx + 1),
                
                # 도메인 메타데이터 (규제 특화)
                'document_type': 'regulation',
                'extraction_timestamp': datetime.utcnow().isoformat() + 'Z',
                
                # 청킹/검색용 메타데이터
                'chunk_source': 'document_loader',
                'parent_document': file_path.stem,
            })
            
            # 규제 도메인 메타데이터 자동 감지
            domain_meta = self._extract_domain_metadata_from_content(doc.page_content)
            enhanced_metadata.update(domain_meta)
            
            # 새 Document 생성 (메타데이터 전파 보장)
            standardized_doc = Document(
                page_content=doc.page_content,
                metadata=enhanced_metadata
            )
            standardized.append(standardized_doc)
        
        return standardized
    
    def _extract_domain_metadata_from_content(self, content: str) -> Dict[str, Any]:
        """
        텍스트 내용에서 규제 도메인 메타데이터 자동 감지.
        """
        domain_meta = {}
        content_lower = content.lower()
        
        # 관할권 자동 감지
        if any(pattern in content_lower for pattern in ['congress', 'federal', 'u.s.c']):
            domain_meta['jurisdiction'] = 'federal'
        elif any(pattern in content_lower for pattern in ['california', 'state', 'division']):
            domain_meta['jurisdiction'] = 'state'
        elif any(pattern in content_lower for pattern in ['city', 'county', 'municipal']):
            domain_meta['jurisdiction'] = 'local'
        
        # 규제 기관 자동 감지
        if 'fda' in content_lower or 'food and drug' in content_lower:
            domain_meta['agency'] = 'FDA'
        elif 'state board' in content_lower:
            domain_meta['agency'] = 'State Board'
        
        # 규제 타입 자동 감지
        if any(kw in content_lower for kw in ['tobacco', 'cigarette', 'nicotine']):
            domain_meta['regulation_type'] = 'tobacco_control'
        
        # 조항 ID 추출 (간단한 패턴)
        section_match = re.search(r'section\s+(\d+)', content_lower)
        if section_match:
            domain_meta['clause_id'] = f"sec_{section_match.group(1)}"
        
        return domain_meta
    
    def batch_extract_metadata(
        self,
        documents: List[Dict[str, str]],
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        여러 문서의 메타데이터를 배치 추출합니다.
        
        Args:
            documents: [{"text": "...", "filename": "..."}, ...]
            show_progress: 진행 상황 로깅 여부
        
        Returns:
            List[Dict[str, Any]]: 추출된 메타데이터 리스트
        """
        results = []
        total = len(documents)
        
        for i, doc in enumerate(documents, 1):
            try:
                metadata = self.extract_metadata(
                    document_text=doc.get("text", ""),
                    filename=doc.get("filename"),
                    source_url=doc.get("source_url")
                )
                results.append(metadata)
                
                if show_progress:
                    logger.info(f"[{i}/{total}] ✅ Extracted: {metadata['title'][:40]}")
            
            except Exception as e:
                logger.error(f"[{i}/{total}] ❌ Error: {str(e)}")
                results.append({"error": str(e), "filename": doc.get("filename")})
        
        logger.info(f"✅ Batch extraction complete: {total} documents processed")
        return results


# ==================== 테스트 헬퍼 함수 ====================

def demo_extract():
    """데모용 메타데이터 추출."""
    extractor = MetadataExtractor()
    
    # 테스트 텍스트 (미국 담배 규제)
    test_doc = """
    PUBLIC LAW 111–31—JUNE 22, 2009
    
    FAMILY SMOKING PREVENTION AND TOBACCO CONTROL
    AND FEDERAL RETIREMENT REFORM
    
    An Act
    To protect the public health by providing the Food and Drug Administration with 
    certain authority to regulate tobacco products...
    
    Be it enacted by the Senate and House of Representatives of 
    the United States of America in Congress assembled,
    """
    
    metadata = extractor.extract_metadata(
        document_text=test_doc,
        filename="family_smoking_prevention_act.txt",
        source_url="https://example.com/law"
    )
    
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_extract()
