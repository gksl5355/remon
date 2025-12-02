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
    BATCH_SYSTEM_PROMPT = """You are a regulatory document structure expert.

You will receive MULTIPLE document pages as images.
For EACH page, you must extract the following:

1. **Markdown Content**: Convert the page to clean Markdown format.
   - Use # for top-level headers (e.g., "Part 1")
   - Use ## for sub-headers (e.g., "Section 1.1")
   - Use ### and deeper levels as needed for subsections
   - Preserve all important text content from the page

2. **Entities**: Extract key entities as a JSON array of OBJECTS:
   [
     {"name": "FDA", "type": "Organization", "context": "regulatory body"}
   ]

   - Each entity MUST be an object with:
     - "name": the surface form of the entity (string)
     - "type": one of "Organization", "Regulation", "Chemical", "Number", or "Unknown"
     - "context": (optional) a short string describing how this entity is used in the page
   - Do NOT return plain strings in the entities array. Always return objects.

3. **Tables**: Extract tables as a JSON array of OBJECTS:
   [
     {
       "headers": ["Item", "Limit"],
       "rows": [["Nicotine", "20mg/mL"]],
       "caption": "Table 1"
     }
   ]

   - "headers": list of column names (array of strings)
   - "rows": list of rows, where each row is an array of strings
   - "caption": (optional) table title or brief description

You MUST return ONLY a single JSON ARRAY at the top level.
Each element of this array represents ONE page and MUST have the following structure:

[
  {
    "page_index": 0,
    "markdown_content": "# Part 1\\n## Section 1.1\\n...",
    "entities": [
      {"name": "FDA", "type": "Organization", "context": "regulatory body"}
    ],
    "tables": [
      {
        "headers": ["Item", "Limit"],
        "rows": [["Nicotine", "20mg/mL"]],
        "caption": "Table 1"
      }
    ]
  },
  {
    "page_index": 1,
    "markdown_content": "# Part 2\\n...",
    "entities": [],
    "tables": []
  }
]

IMPORTANT:
- The top-level response MUST be a valid JSON array.
- Each object in the array MUST correspond to exactly one page.
- The "page_index" MUST be an integer and MUST match the order of images provided
  in the user message (0-based indexing: the first image is page_index 0, the second is 1, etc.).
- If a page has no entities or tables, use empty arrays: "entities": [], "tables": [].
- Do NOT include any explanatory text, comments, or Markdown outside of the JSON array.
Return ONLY the JSON array."""
    
    def __init__(self):
        pass
    
    def extract(self, llm_output: str, page_num: int) -> PageStructure:
        """
        LLM 출력을 구조화 (단일 페이지용, 기존 호환성 유지).
        
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
    
    def extract_batch(self, page_infos: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
        """
        배치 단위 구조화 (여러 페이지를 한 번에 Vision LLM에 전송).
        
        Args:
            page_infos: 페이지 정보 리스트 [{
                "page_index": int,
                "image_base64": str,
                "complexity": float,
                "has_table": bool,
                "model_name": str
            }]
            model: 사용할 모델명 (gpt-4o, gpt-4o-mini)
            
        Returns:
            List[Dict]: 페이지별 구조화 결과 [{
                "page_index": int,
                "page_num": int,
                "model_used": str,
                "content": str,
                "complexity_score": float,
                "tokens_used": int,
                "structure": PageStructure.dict()
            }]
        """
        from openai import OpenAI
        from ..config import PreprocessConfig
        
        config = PreprocessConfig.get_vision_config()
        
        # OpenAI 클라이언트 생성
        client = OpenAI(api_key=config["api_key"], timeout=config["request_timeout"])
        client = PreprocessConfig.wrap_openai_client(client)
        
        # 배치 메시지 구성
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": self.BATCH_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]
            },
            {
                "role": "user",
                "content": self._build_batch_user_content(page_infos)
            }
        ]
        
        logger.info(f"배치 Vision 호출: {model}, {len(page_infos)}페이지")
        
        # Vision API 호출
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=config["max_tokens"],
                temperature=config["temperature"]
            )
            
            batch_content = response.choices[0].message.content
            total_tokens = response.usage.total_tokens
            
            # 배치 결과 파싱
            return self._parse_batch_response(batch_content, page_infos, model, total_tokens)
            
        except Exception as e:
            logger.error(f"배치 Vision 호출 실패 ({model}): {e}")
            # Fallback: 개별 페이지로 처리
            return self._fallback_individual_processing(page_infos, model)
    
    def _build_batch_user_content(self, page_infos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """배치용 사용자 메시지 콘텐츠 구성."""
        content = []
        
        for i, page_info in enumerate(page_infos):
            content.append({
                "type": "text",
                "text": f"Page {i} (original page {page_info['page_index'] + 1}):"
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{page_info['image_base64']}"
                }
            })
        
        content.append({
            "type": "text",
            "text": f"Extract structure from all {len(page_infos)} pages above. Return JSON array."
        })
        
        return content
    
    def _parse_batch_response(
        self, 
        batch_content: str, 
        page_infos: List[Dict[str, Any]], 
        model: str, 
        total_tokens: int
    ) -> List[Dict[str, Any]]:
        """배치 응답 파싱."""
        try:
            # JSON 배열 파싱
            batch_results = self._parse_json_array(batch_content)
            
            if len(batch_results) != len(page_infos):
                logger.warning(
                    f"배치 결과 개수 불일치: 예상 {len(page_infos)}, 실제 {len(batch_results)}"
                )
            
            results = []
            tokens_per_page = total_tokens // len(page_infos) if page_infos else 0
            
            for i, page_info in enumerate(page_infos):
                page_index = page_info["page_index"]
                page_num = page_index + 1
                
                # 해당 페이지 결과 찾기
                page_result = None
                for result in batch_results:
                    if result.get("page_index") == i:
                        page_result = result
                        break
                
                if not page_result:
                    logger.warning(f"페이지 {page_num} 결과 없음, fallback 사용")
                    page_result = {
                        "markdown_content": f"# Page {page_num}\n\nContent extraction failed.",
                        "entities": [],
                        "tables": []
                    }
                
                # PageStructure 생성
                structure = PageStructure(
                    page_num=page_num,
                    markdown_content=page_result.get("markdown_content", ""),
                    entities=[ExtractedEntity(**e) for e in page_result.get("entities", [])],
                    tables=[ExtractedTable(**t) for t in page_result.get("tables", [])]
                )
                
                results.append({
                    "page_index": page_index,
                    "page_num": page_num,
                    "model_used": model,
                    "content": page_result.get("markdown_content", ""),
                    "complexity_score": page_info["complexity"],
                    "tokens_used": tokens_per_page,
                    "structure": structure.dict()
                })
            
            logger.info(f"배치 파싱 완료: {len(results)}페이지, {total_tokens}토큰")
            return results
            
        except Exception as e:
            logger.error(f"배치 응답 파싱 실패: {e}")
            return self._fallback_individual_processing(page_infos, model)
    
    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """JSON 배열 파싱."""
        # JSON 블록 찾기
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "[" in text and "]" in text:
            start = text.find("[")
            end = text.rfind("]") + 1
            json_str = text[start:end]
        else:
            raise json.JSONDecodeError("No JSON array found", text, 0)
        
        return json.loads(json_str)
    
    def _fallback_individual_processing(
        self, 
        page_infos: List[Dict[str, Any]], 
        model: str
    ) -> List[Dict[str, Any]]:
        """배치 실패 시 개별 페이지 처리 fallback."""
        logger.warning(f"배치 처리 실패, 개별 처리로 fallback: {len(page_infos)}페이지")
        
        results = []
        for page_info in page_infos:
            page_index = page_info["page_index"]
            page_num = page_index + 1
            
            # 기본 구조 생성
            structure = PageStructure(
                page_num=page_num,
                markdown_content=f"# Page {page_num}\n\nBatch processing failed, fallback used.",
                entities=[],
                tables=[]
            )
            
            results.append({
                "page_index": page_index,
                "page_num": page_num,
                "model_used": model,
                "content": structure.markdown_content,
                "complexity_score": page_info["complexity"],
                "tokens_used": 100,  # 추정값
                "structure": structure.dict()
            })
        
        return results
    
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
