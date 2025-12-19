"""
module: structure_extractor.py
description: LLM 출력을 구조화된 데이터로 변환 (Pydantic 검증)
author: AI Agent
created: 2025-01-14
updated: 2025-01-22 (프롬프트 분산화 완료)
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
    start_line: int
    end_line: int
    keywords: List[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """문서 메타데이터 (RAG 검색용)."""

    document_id: Optional[str] = None
    doc_type: Optional[str] = None  # "FR" (Federal Register) or "CFR" (Code of Federal Regulations)
    jurisdiction_code: Optional[str] = None
    authority: Optional[str] = None
    title: Optional[str] = None
    citation_code: Optional[str] = None
    language: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    source_url: Optional[str] = None
    retrieval_datetime: Optional[str] = None
    original_format: Optional[str] = None
    file_path: Optional[str] = None
    raw_text_path: Optional[str] = None
    section_label: Optional[str] = None
    page_range: Optional[List[int]] = None
    keywords: List[str] = Field(default_factory=list)
    # 하위 호환성
    country: Optional[str] = None
    regulation_type: Optional[str] = None


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

    def __init__(self, language_code: str = "en"):
        """
        Args:
            language_code: 문서 언어 코드 (en, ru, ko 등)
        """
        self.language_code = language_code.lower()
        
        # 프롬프트 import
        from app.ai_pipeline.prompts.vision_extraction_prompt import (
            VISION_SYSTEM_PROMPT_US,
            VISION_SYSTEM_PROMPT_RU,
            VISION_SYSTEM_PROMPT_ID,
            VISION_BATCH_PROMPT_US,
            VISION_BATCH_PROMPT_RU,
            VISION_BATCH_PROMPT_ID,
        )
        
        self.SYSTEM_PROMPT_US = VISION_SYSTEM_PROMPT_US
        self.SYSTEM_PROMPT_RU = VISION_SYSTEM_PROMPT_RU
        self.SYSTEM_PROMPT_ID = VISION_SYSTEM_PROMPT_ID
        self.BATCH_SYSTEM_PROMPT_US = VISION_BATCH_PROMPT_US
        self.BATCH_SYSTEM_PROMPT_RU = VISION_BATCH_PROMPT_RU
        self.BATCH_SYSTEM_PROMPT_ID = VISION_BATCH_PROMPT_ID
    
    # 기본 프롬프트 속성 (하위 호환성)
    @property
    def SYSTEM_PROMPT(self):
        return self.get_system_prompt()

    @property
    def BATCH_SYSTEM_PROMPT(self):
        return self.get_batch_system_prompt()

    def get_system_prompt(self) -> str:
        """
        언어별 시스템 프롬프트 반환.

        Returns:
            해당 언어의 시스템 프롬프트
        """
        if self.language_code == "ru":
            return self.SYSTEM_PROMPT_RU
        elif self.language_code == "id":
            return self.SYSTEM_PROMPT_ID
        else:
            # 기본값: 영어/미국 (en, ko 등 모두 US 프롬프트 사용)
            return self.SYSTEM_PROMPT_US

    def get_batch_system_prompt(self) -> str:
        """
        언어별 배치 시스템 프롬프트 반환.

        Returns:
            해당 언어의 배치 프롬프트
        """
        if self.language_code == "ru":
            return self.BATCH_SYSTEM_PROMPT_RU
        elif self.language_code == "id":
            return self.BATCH_SYSTEM_PROMPT_ID
        else:
            return self.BATCH_SYSTEM_PROMPT_US

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
                reference_blocks=[
                    ReferenceBlock(**rb) for rb in parsed.get("reference_blocks", [])
                ],
                metadata=(
                    DocumentMetadata(**parsed["metadata"])
                    if parsed.get("metadata")
                    else None
                ),
                entities=[ExtractedEntity(**e) for e in parsed.get("entities", [])],
                tables=[ExtractedTable(**t) for t in parsed.get("tables", [])],
            )

            logger.debug(
                f"페이지 {page_num} 구조화 완료: {len(structure.entities)}개 엔티티, {len(structure.tables)}개 표"
            )

            return structure

        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"페이지 {page_num} 구조화 실패, 원본 텍스트 사용: {e}")

            # Fallback: 원본 텍스트만 사용
            return PageStructure(
                page_num=page_num, markdown_content=llm_output, entities=[], tables=[]
            )

    def extract_batch(
        self, page_infos: List[Dict[str, Any]], model: str
    ) -> List[Dict[str, Any]]:
        """
        배치 단위 구조화 (여러 페이지를 한 번에 Vision LLM에 전송).

        Args:
            page_infos: 페이지 정보 리스트
            model: 사용할 모델명

        Returns:
            List[Dict]: 페이지별 구조화 결과
        """
        from openai import OpenAI
        from ..config import PreprocessConfig

        config = PreprocessConfig.get_vision_config()

        # OpenAI 클라이언트 생성
        client = OpenAI(api_key=config["api_key"], timeout=config["request_timeout"])
        client = PreprocessConfig.wrap_openai_client(client)

        # 배치 메시지 구성 (언어별 프롬프트)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": self.get_batch_system_prompt(),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {"role": "user", "content": self._build_batch_user_content(page_infos)},
        ]

        logger.info(f"배치 Vision 호출: {model}, {len(page_infos)}페이지")

        # Vision API 호출
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
            )

            batch_content = response.choices[0].message.content
            total_tokens = response.usage.total_tokens

            # 배치 결과 파싱
            return self._parse_batch_response(
                batch_content, page_infos, model, total_tokens
            )

        except Exception as e:
            logger.error(f"배치 Vision 호출 실패 ({model}): {e}")
            # Fallback: 개별 페이지로 처리
            return self._fallback_individual_processing(page_infos, model)

    def _build_batch_user_content(
        self, page_infos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """배치용 사용자 메시지 콘텐츠 구성 (통합 문서 처리)."""
        content = [
            {
                "type": "text",
                "text": f"Document images ({len(page_infos)} pages, treat as ONE continuous document):",
            }
        ]

        for page_info in page_infos:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{page_info['image_base64']}"
                    },
                }
            )

        content.append(
            {
                "type": "text",
                "text": "Extract structure from the ENTIRE document above as ONE unified JSON object.",
            }
        )

        return content

    def _parse_batch_response(
        self,
        batch_content: str,
        page_infos: List[Dict[str, Any]],
        model: str,
        total_tokens: int,
    ) -> List[Dict[str, Any]]:
        """배치 응답 파싱 (통합 문서 처리)."""
        try:
            # JSON 객체 파싱 (배열 아님)
            unified_result = self._parse_json(batch_content)

            # 통합된 결과를 페이지별로 분할 (하위 호환성)
            # 실제로는 하나의 통합 결과를 모든 페이지에 복제
            structure = PageStructure(
                page_num=1,  # 통합 문서는 페이지 1로 표시
                markdown_content=unified_result.get("markdown_content", ""),
                reference_blocks=[
                    ReferenceBlock(**rb)
                    for rb in unified_result.get("reference_blocks", [])
                ],
                metadata=(
                    DocumentMetadata(**unified_result["metadata"])
                    if unified_result.get("metadata")
                    else None
                ),
                entities=[
                    ExtractedEntity(**e) for e in unified_result.get("entities", [])
                ],
                tables=[ExtractedTable(**t) for t in unified_result.get("tables", [])],  # ✅ 표 추출 활성화
            )

            # 단일 통합 결과만 반환 (중복 제거)
            result = {
                "page_index": 0,
                "page_num": 1,
                "model_used": model,
                "content": unified_result.get("markdown_content", ""),
                "complexity_score": sum(p["complexity"] for p in page_infos) / len(page_infos),
                "tokens_used": total_tokens,
                "structure": structure.dict(),
            }

            logger.info(
                f"배치 파싱 완료: 통합 문서 ({len(page_infos)}페이지), {total_tokens}토큰"
            )
            return [result]

        except Exception as e:
            logger.error(f"배치 응답 파싱 실패: {e}")
            return self._fallback_individual_processing(page_infos, model)

    def _fallback_individual_processing(
        self, page_infos: List[Dict[str, Any]], model: str
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
                tables=[],
            )

            results.append(
                {
                    "page_index": page_index,
                    "page_num": page_num,
                    "model_used": model,
                    "content": structure.markdown_content,
                    "complexity_score": page_info["complexity"],
                    "tokens_used": 100,  # 추정값
                    "structure": structure.dict(),
                }
            )

        return results

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """LLM 출력에서 JSON 추출 (강화된 파싱)."""
        import re

        # 1. 마크다운 코드 블록 제거
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            # ```만 있는 경우
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            json_str = text

        # 2. JSON 객체 추출
        if "{" in json_str and "}" in json_str:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            json_str = json_str[start:end]
        else:
            raise json.JSONDecodeError("No JSON object found", text, 0)

        # 3. 파싱 시도
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 4. 일반적인 JSON 오류 수정 시도
            # 후행 쉼표 제거
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            return json.loads(json_str)
