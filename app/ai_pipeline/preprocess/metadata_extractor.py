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

from typing import Optional, Dict, Any, List, Tuple
import re
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


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
    
    def __init__(self):
        """초기화."""
        self.patterns = RegulationPatterns()
        logger.info("✅ MetadataExtractor v2 initialized (tobacco-specialized)")
    
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
        """제목 추출."""
        lines = text.strip().split("\n")
        
        for line in lines[:10]:
            line = line.strip()
            
            # 공백 and 특수 문자 제거
            if not line or len(line) < 5 or len(line) > 500:
                continue
            
            # 숫자/로마자만 있는 줄 제외
            if not re.search(r"[가-힣a-zA-Z]", line):
                continue
            
            # 일반적인 제목 길이 체크
            if 10 < len(line) < 300:
                return line
        
        return "제목 미확인"
    
    def _extract_country(self, text: str, filename: Optional[str]) -> str:
        """국가 코드 추출 (텍스트 우선, 파일명은 보조)."""
        text_lower = text.lower()
        
        # 미국 지표 (텍스트 기반)
        us_score = sum([
            2 if re.search(r"united\s+states", text_lower) else 0,
            2 if re.search(r"congress", text_lower) else 0,
            2 if re.search(r"public\s+law\s+\d+[-–]\d+", text_lower) else 0,
            1 if re.search(r"\d+\s+u\.?s\.?c\.?", text_lower) else 0,
            1 if re.search(r"california|florida|texas|new\s+york", text_lower) else 0,
        ])
        
        # 파일명 보조 점수 (낮은 가중치)
        if filename:
            filename_lower = filename.lower()
            if "fda" in filename_lower or "congress" in filename_lower:
                us_score += 1
        
        return "US" if us_score >= 2 else "UNKNOWN"
    
    def _extract_jurisdiction(self, text: str, filename: Optional[str]) -> str:
        """관할권 추출 (federal/state/local)."""
        text_lower = text.lower()
        
        # Federal 확인
        if any(re.search(p, text_lower) for p in self.patterns.FEDERAL_INDICATORS):
            return "federal"
        
        # State 확인
        if any(re.search(p, text_lower) for p in self.patterns.STATE_INDICATORS):
            return "state"
        
        # Local 확인
        if any(re.search(p, text_lower) for p in self.patterns.LOCAL_INDICATORS):
            return "local"
        
        return "unknown"
    
    def _extract_regulatory_body(self, text: str) -> Optional[str]:
        """규제기관 추출 (FDA/State Board/Local Health Dept)."""
        text_lower = text.lower()
        
        for body, patterns in self.patterns.REGULATORY_BODY_MAP.items():
            if any(re.search(p, text_lower) for p in patterns):
                return body
        
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
        """날짜 문자열을 ISO 형식으로 정규화."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # 한국 형식: 2025년1월12일 → 2025-01-12
        match = re.match(r"(\d{4})[년-](\d{1,2})[월-](\d{1,2})[일]?", date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        
        # 표준 형식: 2025-01-12 or 2025/01/12
        match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_str)
        if match:
            year, month, day = match.groups()
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
            return f"{year}-{month_num:02d}-{int(day):02d}"
        
        return None
    
    def _extract_legal_hierarchy(self, text: str) -> Optional[Dict[str, str]]:
        """법률 계층 메타데이터 추출 (CFR/USC/State Law)."""
        hierarchy = {}
        
        # CFR: 21 CFR § 1160.10
        cfr_match = re.search(r'(\d+)\s+CFR\s+§?\s*(\d+)\.(\d+)', text, re.IGNORECASE)
        if cfr_match:
            hierarchy['regulation_type'] = 'CFR'
            hierarchy['title'] = cfr_match.group(1)
            hierarchy['section'] = f"{cfr_match.group(2)}.{cfr_match.group(3)}"
            hierarchy['full_citation'] = f"{cfr_match.group(1)} CFR § {cfr_match.group(2)}.{cfr_match.group(3)}"
        
        # USC: 21 U.S.C. § 387
        usc_match = re.search(r'(\d+)\s+U\.?S\.?C\.?\s+§?\s*(\d+)', text, re.IGNORECASE)
        if usc_match:
            hierarchy['regulation_type'] = 'USC'
            hierarchy['title'] = usc_match.group(1)
            hierarchy['section'] = usc_match.group(2)
            hierarchy['full_citation'] = f"{usc_match.group(1)} U.S.C. § {usc_match.group(2)}"
        
        # State Law: California Section 22977.2
        state_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+.*?[Ss]ection\s+(\d+(?:\.\d+)?)', text)
        if state_match:
            hierarchy['regulation_type'] = 'State Law'
            hierarchy['state'] = state_match.group(1)
            hierarchy['section'] = state_match.group(2)
        
        return hierarchy if hierarchy else None
    
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
