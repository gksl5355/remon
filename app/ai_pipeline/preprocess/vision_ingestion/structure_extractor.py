"""
module: structure_extractor.py
description: LLM 출력을 구조화된 데이터로 변환 (Pydantic 검증)
author: AI Agent
created: 2025-01-14
dependencies: pydantic
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ExtractedEntity(BaseModel):
    """추출된 엔티티."""
    name: str
    type: str  # "Organization", "Regulation", "Chemical", "Number"
    context: Optional[str] = None


class ExtractedTable(BaseModel):
    """추출된 표."""
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = None


class ReferenceBlock(BaseModel):
    """Reference Block (비교 단위)."""
    section_ref: str
    text: str
    start_line: int
    end_line: int
    keywords: List[str] = Field(default_factory=list)

class DocumentMetadata(BaseModel):
    """문서 메타데이터 (RAG 검색용)."""
    title: Optional[str] = None
    country: Optional[str] = None
    regulation_type: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None

class PageStructure(BaseModel):
    """페이지 구조화 데이터."""
    page_num: int
    markdown_content: str
    reference_blocks: List[ReferenceBlock] = Field(default_factory=list)
    metadata: Optional[DocumentMetadata] = None
    entities: List[ExtractedEntity] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)
    hierarchy_level: Optional[str] = None  # "Part", "Section", "Subsection"


class StructureExtractor:
    """LLM 출력을 Pydantic 모델로 변환."""
    
    SYSTEM_PROMPT = """You are a regulatory document structure expert.

Extract the following from the document image:

1. **Markdown Content**: Convert the page to clean Markdown format.
   - Use # for top-level headers (e.g., "Part 1")
   - Use ## for sub-headers (e.g., "Section 1.1")
   - Preserve all text content

2. **Reference Blocks**: Divide content into meaningful reference blocks.
   - Each block should be a complete semantic unit (paragraph, section, or clause)
   - Extract section numbers (e.g., "1114.5(a)(3)")
   - Assign unique reference IDs
   - Keep blocks under 500 words for efficient comparison

3. **Metadata**: Extract document metadata for RAG search.
   - title: Full regulation title
   - country: Country code (e.g., "US", "KR", "EU")
   - regulation_type: Type (e.g., "FDA", "EPA", "MFDS")
   - keywords: Key terms for search (e.g., ["nicotine", "e-cigarette", "20mg/mL"])
   - effective_date: If mentioned (YYYY-MM-DD format)

4. **Entities**: Extract key entities as JSON array:
   [{"name": "FDA", "type": "Organization", "context": "regulatory body"}]
   
5. **Tables**: Extract tables as JSON:
   [{"headers": ["Item", "Limit"], "rows": [["Nicotine", "20mg/mL"]], "caption": "Table 1"}]

**CRITICAL for Reference Blocks:**
- Complete Recall: Include ALL regulatory requirements, prohibitions, and limits
- Context Preservation: Keep numerical values with their context (e.g., "20mg/mL for e-cigarette liquids")
- Search Optimization: Extract keywords that enable accurate database matching

Return ONLY valid JSON in this format:
{
  "markdown_content": "# Part 1\\n## Section 1.1\\n...",
  "reference_blocks": [
    {
      "section_ref": "1114.5(a)(3)",
      "text": "The maximum concentration of nicotine...",
      "start_line": 10,
      "end_line": 25,
      "keywords": ["nicotine", "concentration", "20mg/mL"]
    }
  ],
  "metadata": {
    "title": "Premarket Tobacco Product Applications",
    "country": "US",
    "regulation_type": "FDA",
    "keywords": ["tobacco", "nicotine", "e-cigarette"],
    "effective_date": "2025-01-01"
  },
  "entities": [...],
  "tables": [...]
}"""
    
    def __init__(self):
        pass
    
    def extract(self, llm_output: str, page_num: int) -> PageStructure:
        """
        LLM 출력을 구조화.
        
        Args:
            llm_output: Vision LLM의 원본 출력
            page_num: 페이지 번호
            
        Returns:
            PageStructure: 검증된 구조화 데이터
        """
        try:
            # JSON 파싱 시도
            parsed = self._parse_json(llm_output)
            
            # Pydantic 검증
            structure = PageStructure(
                page_num=page_num,
                markdown_content=parsed.get("markdown_content", llm_output),
                reference_blocks=[ReferenceBlock(**rb) for rb in parsed.get("reference_blocks", [])],
                metadata=DocumentMetadata(**parsed["metadata"]) if parsed.get("metadata") else None,
                entities=[ExtractedEntity(**e) for e in parsed.get("entities", [])],
                tables=[ExtractedTable(**t) for t in parsed.get("tables", [])]
            )
            
            logger.debug(f"페이지 {page_num} 구조화 완료: {len(structure.entities)}개 엔티티, {len(structure.tables)}개 표")
            
            return structure
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"페이지 {page_num} 구조화 실패, 원본 텍스트 사용: {e}")
            
            # Fallback: 원본 텍스트만 사용
            return PageStructure(
                page_num=page_num,
                markdown_content=llm_output,
                entities=[],
                tables=[]
            )
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        """LLM 출력에서 JSON 추출."""
        # JSON 블록 찾기
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            json_str = text[start:end]
        else:
            raise json.JSONDecodeError("No JSON found", text, 0)
        
        return json.loads(json_str)
