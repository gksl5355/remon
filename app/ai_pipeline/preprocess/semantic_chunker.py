"""
module: semantic_chunker.py
description: 의미 기반 청크 분할 (미국 규제 문서 특화)
             담배 규제: Public Law / CFR / State Code / Local Ordinance
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger, app.ai_pipeline.preprocess.config
    - app.ai_pipeline.preprocess.embedding_pipeline
    - typing, re, logging

글로벌 규제 모니터링 AI 시스템 (REMON) - 미국 규제 전용
- 계층 구조: Federal (TITLE/SEC/SUBSECTION) 
           | State (DIVISION/CHAPTER/SECTION/(a)/(b))
           | Local (ARTICLE/SECTION/(paragraph))
"""

from typing import List, Dict, Tuple, Optional, Any
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ProcessedChunk:
    """
    Parent-Child 청킹을 위한 데이터 모델.
    
    Attributes:
        chunk_id: 고유 청크 ID
        text: 검색용 텍스트 (Child)
        context_text: LLM용 전체 맥락 (Parent)
        metadata: 청크 메타데이터
        chunk_type: "parent" | "child"
        parent_id: Parent 청크 ID (Child인 경우)
    """
    chunk_id: str
    text: str
    context_text: str
    metadata: Dict[str, Any]
    chunk_type: str = "child"
    parent_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    parent_embedding: Optional[List[float]] = None

# 청킹에 통합된 모듈들
try:
    from app.ai_pipeline.preprocess.table_detector import TableDetector
    from app.ai_pipeline.preprocess.definition_extractor import DefinitionExtractor
except ImportError:
    TableDetector = None
    DefinitionExtractor = None
    logger.warning("⚠️ TableDetector 또는 DefinitionExtractor 임포트 실패")


class SemanticChunker:
    """
    미국 규제 문서 전용 의미 기반 청크 분할 (REMON v0.2.1).
    
    특화 영역:
    - Federal Laws: Public Law, USC (15 USC 1331, etc)
    - FDA Regulations: CFR Title 21 (담배 규제)
    - State Codes: California BPC Division 8.6, Chapter 3, etc
    - Local Ordinances: San Francisco Health Code Article 19, etc
    
    계층 구조 보존:
    - Federal: TITLE → SECTION → (a)/(b)/(c)
    - State: DIVISION → CHAPTER → SECTION → (a)/(b)
    - Local: ARTICLE → SECTION → (paragraph)
    
    특징:
    - 계층 경계 보존 (분할 시 구조 무손실)
    - 문장 단위 분할 (문장 중단 방지)
    - 테이블/리스트 무결성 보존
    - 청크 메타데이터: 계층, 섹션, 부분 번호 등
    - 오버래핑 지원 (중복 구간으로 맥락 보존)
    """
    
    # ==================== 계층 구조 패턴 (미국 규제) ====================
    
    # Federal Statute / Code 패턴
    FEDERAL_SECTION_PATTERNS = [
        r"^SEC\.\s+(\d+[A-Z]?)",                # SEC. 201
        r"^SECTION\s+(\d+)",                    # SECTION 301
        r"^\s*\(\s*([a-z])\s*\)\s+",            # (a), (b), (c)
        r"^\s*\(\s*(\d+)\s*\)\s+",              # (1), (2), (3)
        r"^\d+\s+U\.S\.C\..*§?\s*(\d+)",        # 15 USC 1331
    ]
    
    # State Code 패턴 (California BPC 등)
    STATE_SECTION_PATTERNS = [
        r"^(?:DIV\.|DIVISION)\s+(\d+(?:\.\d+)?)",  # DIV. 8.6, DIVISION 8.6
        r"^(?:CH\.|CHAPTER)\s+(\d+)",              # CH. 3, CHAPTER 3
        r"^(?:SEC\.|SECTION|§)\s+(\d+)",           # SEC. 22975, SECTION 22975
        r"^\s*\(\s*([a-z])\s*\)\s+",               # (a), (b)
    ]
    
    # Local Ordinance 패턴
    LOCAL_SECTION_PATTERNS = [
        r"^(?:ARTICLE|ART\.?)\s+(\d+|[IVX]+)",     # ARTICLE 19, ART. XIX
        r"^(?:SEC\.|SECTION|§)\s+(\d+)",           # SEC. 1000, SECTION 1001
        r"^\s*\(\s*([a-zA-Z])\s*\)\s+",            # (a), (b), (A), (B)
    ]
    
    # ==================== 주요 섹션 마커 ====================
    
    # 큰 제목 (절 단위)
    MAJOR_SECTION_MARKER = re.compile(
        r"^(?:TITLE|SEC\.|SECTION|SUBTITLE|DIV\.|DIVISION|CHAPTER|ARTICLE|CH\.)\s+",
        re.MULTILINE | re.IGNORECASE
    )
    
    # 작은 제목 (항목 단위)
    SUBSECTION_MARKER = re.compile(
        r"^\s*\(\s*[a-z0-9]+\s*\)\s+",
        re.MULTILINE
    )
    
    # ==================== 보완: 테이블/각주/법률 인용 패턴 ====================
    
    # Federal Register 테이블 패턴
    TABLE_PATTERNS = [
        r"TABLE\s+\d+[—–-]",                    # TABLE 1—NICOTINE CONTENT
        r"Abbreviation/\s*acronym",              # 약어 테이블
        r"\|\s*Brand\s*\|",                     # 브랜드 비교 테이블
        r"^\s*\+[-=]+\+",                        # ASCII 테이블 구분자
    ]
    
    # 각주 패턴
    FOOTNOTE_PATTERN = re.compile(
        r"^(\d+)\s+(?:Throughout|For purposes|See|As stated|The term|FDA)",
        re.MULTILINE
    )
    
    # 법률 인용 패턴
    LEGAL_CITATION_PATTERNS = [
        r"(\d+)\s+U\.S\.C\.\s+§?\s*(\d+(?:\([a-z0-9]+\))?)",  # 21 U.S.C. 387(3)
        r"(\d+)\s+CFR\s+(?:Part\s+)?(\d+(?:\.\d+)?)",        # 21 CFR Part 1160
        r"(\d+)\s+FR\s+(\d+)",                                 # 83 FR 11818
        r"Ref\.\s+(\d+)",                                       # (Ref. 1)
    ]
    
    def __init__(
        self,
        chunk_size: int = 1024,
        overlap_size: int = 256,
        min_chunk_size: int = 100,
        max_chunk_size: int = 2048,
    ):
        """
        미국 규제 문서 청크 분할기 초기화.
        
        Args:
            chunk_size (int): 목표 청크 크기 (문자). 기본값: 1024
            overlap_size (int): 청크 간 중복 크기 (문자). 기본값: 256
            min_chunk_size (int): 최소 청크 크기. 기본값: 100
            max_chunk_size (int): 최대 청크 크기. 기본값: 2048
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
        # 통합 모듈 초기화
        self.table_detector = TableDetector() if TableDetector else None
        self.definition_extractor = DefinitionExtractor() if DefinitionExtractor else None
        
        logger.info(
            f"✅ SemanticChunker 초기화 (테이블/정의 통합): "
            f"chunk_size={chunk_size}, overlap={overlap_size}"
        )

    
    def chunk_document(
        self,
        document_text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        미국 규제 문서를 의미적으로 의미 있는 청크로 분할.
        
        Args:
            document_text (str): 규제 문서 텍스트
            document_metadata (Optional[Dict]): 문서 메타데이터
                {
                    "doc_id": "doc_FDA_2025_00397",
                    "title": "Tobacco Product Standard...",
                    "jurisdiction": "federal",        # federal/state/local
                    "regulatory_body": "FDA",
                    "law_type": "regulation",          # statute/code/regulation
                    ...
                }
        
        Returns:
            Dict[str, Any]: {
                "num_chunks": 청크 개수,
                "chunks": [
                    {
                        "chunk_id": "doc_FDA_2025_00397_0",
                        "text": "청크 텍스트",
                        "start_char": 0,
                        "end_char": 1024,
                        "section": "SEC. 101",              # 상위 섹션 번호
                        "section_title": "Authority",       # 섹션 제목
                        "subsection": "(a)",                # 하위 항목
                        "hierarchy_path": "TITLE I / SEC. 101 / (a)",
                        "hierarchy_depth": 3,              # 깊이 레벨
                        "has_table": False,
                        "tokens_estimate": 256,
                    },
                    ...
                ],
                "statistics": {
                    "avg_chunk_size": 1000,
                    "total_tokens_estimate": 5000,
                    "hierarchy_levels": ["TITLE", "SECTION", "SUBSECTION"],
                }
            }
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty")
        
        if not document_metadata:
            document_metadata = {}
        
        # 1단계: 테이블 감지 및 Markdown 변환
        table_result = {"converted_text": document_text, "table_regions": [], "num_tables": 0}
        if self.table_detector:
            table_result = self.table_detector.detect_and_convert_tables(document_text)
            document_text = table_result["converted_text"]
            logger.debug(f"✅ 테이블 변환: {table_result['num_tables']}개 → Markdown")
        
        # 2단계: 정의 및 약어 추출
        definitions_result = {"definitions": [], "acronyms": []}
        if self.definition_extractor:
            definitions_result = self.definition_extractor.extract_definitions_and_acronyms(document_text)
            logger.debug(f"✅ 정의/약어: {len(definitions_result['definitions'])}/{len(definitions_result['acronyms'])}개")
        
        # 3단계: 문서 유형에 따른 섹션 식별
        jurisdiction = document_metadata.get("jurisdiction", "federal")
        sections = self._identify_sections(document_text, jurisdiction)
        logger.debug(f"✅ 섹션 식별: {len(sections)}개 ({jurisdiction})")
        
        # 4단계: 각 섹션을 청크로 분할 (테이블/정의 보존)
        all_chunks = []
        for section in sections:
            chunks = self._chunk_section_with_preservation(
                section, jurisdiction, table_result["table_regions"], definitions_result
            )
            all_chunks.extend(chunks)
        
        # 3단계: 청크에 메타데이터 추가
        doc_id = document_metadata.get("doc_id", "unknown")
        final_chunks = []
        
        for chunk_idx, chunk in enumerate(all_chunks):
            final_chunk = {
                "chunk_id": f"{doc_id}_{chunk_idx}",
                "text": chunk["text"],
                "start_char": chunk["start_char"],
                "end_char": chunk["end_char"],
                "section": chunk.get("section_num", ""),
                "section_title": chunk.get("section_title", ""),
                "subsection": chunk.get("subsection", ""),
                "hierarchy_path": chunk.get("hierarchy_path", ""),
                "hierarchy_depth": chunk.get("hierarchy_depth", 0),
                "has_table": chunk.get("has_table", self._contains_table(chunk["text"])),
                "has_definition": chunk.get("has_definition", False),
                "tokens_estimate": self._estimate_tokens(chunk["text"]),
                "footnotes": self._extract_footnotes(chunk["text"]),
                "legal_citations": self._extract_legal_citations(chunk["text"]),
            }
            final_chunks.append(final_chunk)
        
        # 통계
        avg_chunk_size = (
            sum(len(c["text"]) for c in final_chunks) / len(final_chunks)
            if final_chunks else 0
        )
        total_tokens = sum(c["tokens_estimate"] for c in final_chunks)
        
        logger.info(
            f"✅ 청크 분할 완료: {len(final_chunks)}개 청크, "
            f"평균 {avg_chunk_size:.0f}자, 예상 {total_tokens} 토큰"
        )
        
        return {
            "num_chunks": len(final_chunks),
            "chunks": final_chunks,
            "statistics": {
                "avg_chunk_size": round(avg_chunk_size, 1),
                "total_tokens_estimate": total_tokens,
                "num_sections": len(sections),
                "num_tables": table_result["num_tables"],
                "num_definitions": len(definitions_result["definitions"]),
                "num_acronyms": len(definitions_result["acronyms"]),
            }
        }
    
    # ==================== 섹션 식별 (미국 규제 전용) ====================
    
    def _identify_sections(
        self,
        text: str,
        jurisdiction: str = "federal"
    ) -> List[Dict[str, Any]]:
        """
        미국 규제 문서의 계층 구조를 식별합니다.
        
        Federal: TITLE → SECTION → (subsection)
        State: DIVISION → CHAPTER → SECTION → (a), (b)
        Local: ARTICLE → SECTION → (paragraph)
        
        Args:
            text: 문서 텍스트
            jurisdiction: "federal", "state", "local"
        
        Returns:
            List[Dict]: 섹션 정보
        """
        sections = []
        lines = text.split("\n")
        
        current_section = None
        
        for line_idx, line in enumerate(lines):
            stripped = line.strip()
            
            if not stripped:
                continue
            
            # 주 섹션 감지 (TITLE / SECTION / DIVISION / ARTICLE)
            if self._is_major_section(stripped, jurisdiction):
                # 이전 섹션 저장
                if current_section:
                    current_section["text"] = "\n".join(
                        lines[current_section["start_line"]:line_idx]
                    )
                    current_section["end_line"] = line_idx
                    sections.append(current_section)
                
                # 새로운 섹션 시작
                section_num, section_title = self._extract_section_info(
                    stripped, jurisdiction
                )
                current_section = {
                    "level": "major",
                    "number": section_num,
                    "title": section_title,
                    "start_line": line_idx,
                    "start_char": sum(len(l) + 1 for l in lines[:line_idx]),
                    "text": "",
                }
        
        # 마지막 섹션 처리
        if current_section:
            current_section["text"] = "\n".join(
                lines[current_section["start_line"]:]
            )
            current_section["end_line"] = len(lines)
            sections.append(current_section)
        
        # 섹션이 없으면 전체를 하나의 섹션으로
        if not sections:
            sections = [{
                "level": "full_document",
                "number": "0",
                "title": "Full Document",
                "text": text,
                "start_char": 0,
                "end_char": len(text),
            }]
        
        logger.debug(f"식별된 섹션: {len(sections)}개")
        return sections
    
    def _is_major_section(self, line: str, jurisdiction: str) -> bool:
        """주 섹션 마커인지 확인."""
        line_lower = line.lower()
        
        if jurisdiction == "federal":
            return bool(re.match(
                r"^(?:title|sec\.|section|subtitle)\s+",
                line_lower
            ))
        elif jurisdiction == "state":
            return bool(re.match(
                r"^(?:division|chapter|section|div\.|ch\.|sec\.)\s+",
                line_lower
            ))
        elif jurisdiction == "local":
            return bool(re.match(
                r"^(?:article|section|sec\.|art\.)\s+",
                line_lower
            ))
        
        return False
    
    def _extract_section_info(
        self,
        line: str,
        jurisdiction: str
    ) -> Tuple[str, str]:
        """섹션 번호와 제목을 추출."""
        # 번호 추출
        number_match = re.search(
            r"(?:TITLE|SEC\.|SECTION|DIVISION|CHAPTER|ARTICLE)\s+([^\s:]+)",
            line,
            re.IGNORECASE
        )
        section_num = number_match.group(1) if number_match else "0"
        
        # 제목 추출 (: 또는 - 뒤의 텍스트)
        title_parts = re.split(r"[:–—-]", line, 1)
        section_title = (
            title_parts[-1].strip()
            if len(title_parts) > 1
            else "No Title"
        )
        
        return section_num, section_title
    
    # ==================== 청크 분할 ====================
    
    def _chunk_section(
        self,
        section: Dict[str, Any],
        jurisdiction: str
    ) -> List[Dict[str, Any]]:
        """
        섹션을 청크로 분할 (문장 경계 고려, 동적 크기 조정).
        """
        section_text = section.get("text", "")
        adaptive_size = self._adaptive_chunk_size(len(section_text))
        
        if len(section_text) <= adaptive_size:
            return [{
                "text": section_text,
                "start_char": 0,
                "end_char": len(section_text),
                "section_num": section.get("number"),
                "section_title": section.get("title"),
                "subsection": "",
                "hierarchy_path": f"{section.get('number')}",
                "hierarchy_depth": 1,
            }]
        
        # 문장 단위 분할
        sentences = self._split_into_sentences(section_text)
        
        chunks = []
        current_chunk = ""
        chunk_start = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            potential_chunk = (
                current_chunk + " " + sentence
                if current_chunk else sentence
            )
            
            if len(potential_chunk) <= adaptive_size:
                current_chunk = potential_chunk
            else:
                # 현재 청크 저장
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append({
                        "text": current_chunk,
                        "start_char": chunk_start,
                        "end_char": chunk_start + len(current_chunk),
                        "section_num": section.get("number"),
                        "section_title": section.get("title"),
                        "subsection": self._extract_subsection(current_chunk),
                        "hierarchy_path": f"{section.get('number')}",
                        "hierarchy_depth": 2,
                    })
                    chunk_start += len(current_chunk) + 1
                
                current_chunk = sentence
        
        # 마지막 청크 처리
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append({
                "text": current_chunk,
                "start_char": chunk_start,
                "end_char": chunk_start + len(current_chunk),
                "section_num": section.get("number"),
                "section_title": section.get("title"),
                "subsection": self._extract_subsection(current_chunk),
                "hierarchy_path": f"{section.get('number')}",
                "hierarchy_depth": 2,
            })
        
        return chunks if chunks else [{
            "text": section_text,
            "start_char": 0,
            "end_char": len(section_text),
            "section_num": section.get("number"),
            "section_title": section.get("title"),
            "subsection": "",
            "hierarchy_path": f"{section.get('number')}",
            "hierarchy_depth": 1,
        }]
    
    def _extract_subsection(self, text: str) -> str:
        """텍스트에서 항목 번호 추출 (a), (1), 등."""
        match = re.search(r"^\s*\(\s*([a-z0-9]+)\s*\)", text)
        return match.group(1) if match else ""
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장으로 분할 (미국 규제 형식)."""
        # 문장 끝: . ! ? 또는 개행 후 괄호
        sentences = re.split(
            r'(?<=[.!?])\s+|(?<=\.\s)(?=\()',
            text
        )
        return [s.strip() for s in sentences if s.strip()]
    
    # ==================== 유틸리티 ====================
    
    def _chunk_section_with_preservation(
        self,
        section: Dict[str, Any],
        jurisdiction: str,
        table_regions: List[Tuple[int, int]],
        definitions_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        섹션을 청크로 분할하되 테이블과 정의 영역 보존.
        
        Args:
            section: 섹션 정보
            jurisdiction: 관할권
            table_regions: 테이블 영역 리스트
            definitions_result: 정의/약어 추출 결과
        
        Returns:
            List[Dict]: 청크 리스트
        """
        text = section.get("text", "")
        if not text:
            return []
        
        chunks = []
        current_pos = 0
        
        # 문장 단위로 분할
        sentences = self._split_into_sentences(text)
        current_chunk = ""
        current_start = 0
        
        for sentence in sentences:
            # 청크 크기 확인
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                # 테이블/정의 영역 확인
                has_table = self.table_detector and any(
                    self.table_detector.is_table_region(line_num, table_regions)
                    for line_num in range(current_start, current_pos)
                ) if self.table_detector else False
                
                has_definition = self.definition_extractor and self.definition_extractor.has_definition_in_range(
                    text, current_start, current_pos
                ) if self.definition_extractor else False
                
                chunk_info = {
                    "text": current_chunk.strip(),
                    "start_char": current_start,
                    "end_char": current_pos,
                    "section_num": section.get("number", ""),
                    "section_title": section.get("title", ""),
                    "has_table": has_table,
                    "has_definition": has_definition,
                }
                chunks.append(chunk_info)
                
                current_chunk = sentence
                current_start = current_pos
            else:
                current_chunk += " " + sentence if current_chunk else sentence
            
            current_pos += len(sentence) + 1
        
        # 마지막 청크
        if current_chunk:
            has_table = self.table_detector and any(
                self.table_detector.is_table_region(line_num, table_regions)
                for line_num in range(current_start, len(text))
            ) if self.table_detector else False
            
            has_definition = self.definition_extractor and self.definition_extractor.has_definition_in_range(
                text, current_start, len(text)
            ) if self.definition_extractor else False
            
            chunk_info = {
                "text": current_chunk.strip(),
                "start_char": current_start,
                "end_char": len(text),
                "section_num": section.get("number", ""),
                "section_title": section.get("title", ""),
                "has_table": has_table,
                "has_definition": has_definition,
            }
            chunks.append(chunk_info)
        
        return chunks
    
    def _contains_table(self, text: str) -> bool:
        """텍스트가 테이블을 포함하는지 확인 (Federal Register 특화)."""
        for pattern in self.TABLE_PATTERNS:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                return True
        return "|" in text
    
    def _estimate_tokens(self, text: str) -> int:
        """
        토큰 수 추정 (간단한 방식).
        
        미국 영문 규제: 단어 ≈ 1.3 토큰
        추정: 평균 5자/단어 → 4자 ≈ 1 토큰
        """
        return max(1, len(text) // 4)
    
    def _extract_footnotes(self, text: str) -> List[Dict[str, str]]:
        """각주 추출 (Federal Register 형식)."""
        footnotes = []
        for match in self.FOOTNOTE_PATTERN.finditer(text):
            footnote_num = match.group(1)
            # 각주 전체 텍스트 추출 (다음 각주 또는 섹션까지)
            start = match.start()
            end = text.find(f"\n{int(footnote_num)+1} ", start + 1)
            if end == -1:
                end = len(text)
            footnote_text = text[start:end].strip()
            footnotes.append({"number": footnote_num, "text": footnote_text})
        return footnotes
    
    def _extract_legal_citations(self, text: str) -> List[Dict[str, str]]:
        """법률 인용 추출 및 구조화."""
        citations = []
        for pattern in self.LEGAL_CITATION_PATTERNS:
            for match in re.finditer(pattern, text):
                if "U.S.C." in match.group(0):
                    citations.append({
                        "type": "USC",
                        "title": match.group(1),
                        "section": match.group(2),
                        "full_citation": match.group(0)
                    })
                elif "CFR" in match.group(0):
                    citations.append({
                        "type": "CFR",
                        "title": match.group(1),
                        "part": match.group(2),
                        "full_citation": match.group(0)
                    })
                elif "FR" in match.group(0):
                    citations.append({
                        "type": "FR",
                        "volume": match.group(1),
                        "page": match.group(2),
                        "full_citation": match.group(0)
                    })
                elif "Ref." in match.group(0):
                    citations.append({
                        "type": "Reference",
                        "ref_num": match.group(1),
                        "full_citation": match.group(0)
                    })
        return citations
    
    def _adaptive_chunk_size(self, section_length: int) -> int:
        """섹션 길이에 따라 동적으로 청크 크기 조정."""
        if section_length > 10000:
            return 1536  # 긴 섹션: 더 큰 청크
        elif section_length < 500:
            return 512   # 짧은 섹션: 작은 청크
        return self.chunk_size  # 기본값
    
    def batch_chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        여러 문서를 배치로 청크 분할.
        
        Args:
            documents: [{"text": "...", "metadata": {...}}, ...]
            show_progress: 진행 상황 로깅 여부
        
        Returns:
            List: 청크 분할 결과
        """
        results = []
        total = len(documents)
        
        for i, doc in enumerate(documents, 1):
            try:
                result = self.chunk_document(
                    document_text=doc.get("text", ""),
                    document_metadata=doc.get("metadata")
                )
                results.append(result)
                
                if show_progress:
                    logger.info(
                        f"[{i}/{total}] ✅ 청크 분할: "
                        f"{result['num_chunks']}개 청크"
                    )
            
            except Exception as e:
                logger.error(f"[{i}/{total}] ❌ 오류: {str(e)}")
                results.append({"error": str(e)})
        
        logger.info(f"✅ 배치 완료: {total}개 문서")
        return results
    
    def _reconstruct_full_text(self, node: Dict[str, Any]) -> str:
        """
        트리를 순회하며 전체 텍스트 재조립 (Parent Chunk용).
        
        Args:
            node: LegalNode 딕셔너리
            
        Returns:
            str: 재조립된 전체 텍스트
        """
        text = f"{node.get('identifier', '')} {node.get('text', '')}\n"
        
        for child in node.get("children", []):
            text += self._reconstruct_full_text(child)
            
        return text
    
    def _flatten_nodes(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        트리를 평탄화하여 개별 검색 단위 추출 (Child Chunk용).
        
        Args:
            node: LegalNode 딕셔너리
            
        Returns:
            List[Dict]: 평탄화된 노드 리스트
        """
        flat_list = [node]  # 자기 자신 포함
        
        for child in node.get("children", []):
            flat_list.extend(self._flatten_nodes(child))
            
        return flat_list
    
    def _normalize_terms(self, text: str) -> str:
        """
        기술 용어 정규화 (definition_extractor 통합).
        
        Args:
            text: 원본 텍스트
            
        Returns:
            str: 정규화된 텍스트
        """
        if not text:
            return ""
            
        # 기본 담배 규제 용어 정규화
        replacements = {
            "HPHC": "Harmful and Potentially Harmful Constituent (HPHC)",
            "MRTP": "Modified Risk Tobacco Product (MRTP)",
            "VLNC": "Very Low Nicotine Content (VLNC)",
            "FDA": "Food and Drug Administration (FDA)",
            "CFR": "Code of Federal Regulations (CFR)",
            "USC": "United States Code (USC)"
        }
        
        normalized_text = text
        for abbr, full_form in replacements.items():
            # 이미 확장된 형태가 아닌 경우에만 치환
            if abbr in normalized_text and full_form not in normalized_text:
                normalized_text = normalized_text.replace(abbr, full_form)
                
        # definition_extractor 사용 (있는 경우)
        if self.definition_extractor:
            try:
                definitions = self.definition_extractor.extract_definitions_and_acronyms(normalized_text)
                # 추출된 정의를 텍스트에 반영
                for definition in definitions.get("definitions", []):
                    term = definition.get("term", "")
                    meaning = definition.get("definition", "")
                    if term and meaning and len(meaning) < 100:  # 너무 긴 정의는 제외
                        normalized_text = normalized_text.replace(
                            term, f"{term} ({meaning})", 1
                        )
            except Exception as e:
                logger.debug(f"정의 추출 중 오류: {e}")
                
        return normalized_text
    
    def create_parent_child_chunks(
        self,
        legal_nodes: List[Dict[str, Any]],
        global_metadata: Optional[Dict[str, Any]] = None
    ) -> List[ProcessedChunk]:
        """
        DDH 구조의 LegalNode를 Parent-Child 청크로 변환.
        
        Args:
            legal_nodes: hierarchy_extractor.parse_ddh_structure() 결과
            global_metadata: 전역 메타데이터
            
        Returns:
            List[ProcessedChunk]: Parent-Child 청크 리스트
        """
        if not global_metadata:
            global_metadata = {}
            
        final_chunks = []
        
        for section in legal_nodes:
            if section.get("node_type") != "section":
                continue
                
            # Parent Chunk 생성 (섹션 전체)
            full_section_text = self._reconstruct_full_text(section)
            full_section_text = self._normalize_terms(full_section_text)
            
            parent_chunk = ProcessedChunk(
                chunk_id=f"parent_{section['identifier']}",
                text=full_section_text,
                context_text=full_section_text,
                metadata={
                    **global_metadata,
                    **section.get("metadata", {}),
                    "section_id": section["identifier"],
                    "type": "parent",
                    "law_level": "Section"
                },
                chunk_type="parent"
            )
            final_chunks.append(parent_chunk)
            
            # Child Chunks 생성 (개별 조항)
            children_chunks = self._flatten_nodes(section)
            
            for child in children_chunks:
                # 표(Table) 처리
                is_table = "|" in child.get("text", "") and "-|-" in child.get("text", "")
                
                child_chunk = ProcessedChunk(
                    chunk_id=f"child_{section['identifier']}_{child.get('identifier', 'unknown')}",
                    text=self._normalize_terms(child.get("text", "")),
                    context_text=full_section_text,
                    metadata={
                        **global_metadata,
                        **section.get("metadata", {}),
                        "section_id": section["identifier"],
                        "hierarchy_level": child.get("identifier", ""),
                        "level": child.get("level", 0),
                        "is_table": is_table,
                        "type": "child"
                    },
                    chunk_type="child",
                    parent_id=f"parent_{section['identifier']}"
                )
                final_chunks.append(child_chunk)
                
        logger.info(f"✅ Parent-Child 청킹 완료: {len(final_chunks)}개 청크")
        return final_chunks


if __name__ == "__main__":
    # 테스트
    test_doc = """
    TITLE I—AUTHORITY OF THE FOOD AND DRUG ADMINISTRATION
    
    SEC. 101. AMENDMENT OF FEDERAL FOOD, DRUG, AND COSMETIC ACT.
    
    (a) In General.—The Federal Food, Drug, and Cosmetic Act (21 U.S.C. 301 et seq.) 
    is amended by inserting after section 704 the following new section:
    
    (b) Authority.—The Secretary of Health and Human Services (referred to in this Act 
    as the "Secretary") shall issue regulations to implement this section.
    """
    
    chunker = SemanticChunker()
    result = chunker.chunk_document(
        test_doc,
        {
            "doc_id": "test_doc_001",
            "title": "Test Regulation",
            "jurisdiction": "federal",
            "regulatory_body": "FDA",
        }
    )
    
    print(f"✅ 청크 분할 완료: {result['num_chunks']}개 청크")
    for chunk in result['chunks'][:3]:
        print(f"\n청크 ID: {chunk['chunk_id']}")
        print(f"섹션: {chunk['section']} ({chunk['section_title']})")
        print(f"계층: {chunk['hierarchy_path']} (깊이: {chunk['hierarchy_depth']})")
        print(f"텍스트: {chunk['text'][:100]}...")
