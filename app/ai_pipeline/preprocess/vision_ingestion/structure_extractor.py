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


class PageStructure(BaseModel):
    """페이지 구조화 데이터."""
    page_num: int
    markdown_content: str
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

2. **Entities**: Extract key entities as JSON array:
   [{"name": "FDA", "type": "Organization", "context": "regulatory body"}]
   
3. **Tables**: Extract tables as JSON:
   [{"headers": ["Item", "Limit"], "rows": [["Nicotine", "20mg/mL"]], "caption": "Table 1"}]

Return ONLY valid JSON in this format:
{
  "markdown_content": "# Part 1\\n## Section 1.1\\n...",
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
