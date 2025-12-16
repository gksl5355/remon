"""
LLM 번역기 구현.

- 테스트용/프로덕션용 동일 프롬프트 경로를 사용하도록 prompts 모듈로 분리.
- glossary는 data/glossary/{name}.json 형태로 로드 가능.
- 큰 문서는 batch_pages 단위로 쪼개어 호출.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI

from app.ai_pipeline.prompts.translation_prompt import (
    build_translation_prompt,
    build_markdown_translation_prompt,
)

logger = logging.getLogger(__name__)


class LLMTranslator:
    """LLM 기반 번역기"""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        glossary_dir: Path | None = None,
        batch_pages: int = 1,
    ):
        # 우선순위: 인자 > 환경변수 LLM_TRANSLATION_MODEL > 기본값 gpt-5-mini
        self.model = model or os.getenv("LLM_TRANSLATION_MODEL") or "gpt-5-mini"
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.glossary_dir = glossary_dir or (Path("data") / "glossary")
        self.batch_pages = max(1, batch_pages)

    def load_glossary(self, name: Optional[str]) -> Dict[str, str]:
        """data/glossary/{name}에서 glossary JSON을 로드한다."""
        if not name:
            return {}
        path = self.glossary_dir / name
        if not path.exists():
            logger.warning("Glossary file not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to load glossary %s: %s", path, e)
            return {}

    async def translate(
        self,
        *,
        pages: List[Dict[str, Any]],
        target_lang: str,
        glossary: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        입력 pages(JSON) → 번역된 JSON 전체를 반환한다.
        batch_pages 단위로 쪼개어 LLM을 호출한다.
        """
        results: List[Dict[str, Any]] = []
        # glossary 사용 안 함 (테스트용)
        glossary = {}

        for i in range(0, len(pages), self.batch_pages):
            batch = pages[i : i + self.batch_pages]
            prompt = build_translation_prompt(batch, glossary)
            translated_str = await self._call_llm(prompt)
            translated_json = self._safe_parse_json(translated_str)
            results.append(
                {
                    "batch_index": len(results),
                    "pages": [p.get("page") for p in batch],
                    "translated_json": translated_json
                    if translated_json is not None
                    else translated_str,
                }
            )

        return {
            "model": self.model,
            "target_lang": target_lang,
            "glossary_used": bool(glossary),
            "results": results,
        }

    async def translate_markdown(
        self,
        *,
        pages: List[Dict[str, Any]],
        target_lang: str,
        glossary: Optional[Dict[str, str]] = None,
        save_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Markdown 구조를 번역한다. 페이지 목록은 page_num, markdown_content를 포함해야 한다.
        """
        results: List[Dict[str, Any]] = []
        glossary = {}
        page_order = [p.get("page") or p.get("page_num") for p in pages]

        for i in range(0, len(pages), self.batch_pages):
            batch = pages[i : i + self.batch_pages]
            # prompt expects {"page": n, "markdown": "..."}
            norm_batch = []
            for p in batch:
                norm_batch.append(
                    {
                        "page": p.get("page") or p.get("page_num"),
                        "markdown": p.get("markdown") or p.get("markdown_content"),
                    }
                )
            prompt = build_markdown_translation_prompt(norm_batch, glossary)
            translated_str = await self._call_llm(prompt)
            parsed = self._safe_parse_json(translated_str)

            # 보정: page 번호가 누락된 경우 입력 배치 순서로 채움
            if isinstance(parsed, list):
                for idx, item in enumerate(parsed):
                    if isinstance(item, dict) and item.get("page") is None:
                        if idx < len(norm_batch):
                            item["page"] = norm_batch[idx].get("page")

            batch_result = {
                "batch_index": len(results),
                "pages": [p.get("page") for p in norm_batch],
                "translated": parsed if parsed is not None else translated_str,
                "source": norm_batch,
                "raw_response": translated_str,
            }
            results.append(batch_result)

            # 배치별 저장 (재시도/복구용)
            if save_dir:
                save_dir.mkdir(parents=True, exist_ok=True)
                out_path = save_dir / f"translation_batch_{len(results)-1}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(batch_result, f, ensure_ascii=False, indent=2)

        return {
            "model": self.model,
            "target_lang": target_lang,
            "glossary_used": bool(glossary),
            "page_order": page_order,
            "results": results,
        }

    async def _call_llm(self, prompt: str) -> str:
        """
        OpenAI Chat Completions API 호출 (AsyncOpenAI + openai==2.8.0)
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
            )

            return response.choices[0].message.content

        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed: %s", e, exc_info=True)
            raise


    def _safe_parse_json(self, text: str) -> Optional[dict]:
        """LLM 응답을 JSON으로 파싱, 실패 시 None"""
        try:
            return json.loads(text)
        except Exception:
            return None
