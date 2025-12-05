"""
LLM 기반 종합 리포트 생성기.

- 기간(start/end)과 집계된 항목(items)을 받아 LLM으로 HTML 본문을 생성한다.
- 최종 출력은 한글이며, HTML만 반환하도록 강제한다.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class CombinedReportGenerator:
    """기간별 종합 리포트를 생성하기 위한 LLM 호출기"""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("LLM_COMBINED_MODEL") or "gpt-5-mini"
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate(
        self,
        *,
        start_date: str,
        end_date: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        기간/데이터를 받아 종합 리포트 HTML을 생성한다.
        """
        prompt = self._build_prompt(start_date, end_date, items)
        try:
            html_body = await self._call_llm(prompt)
        except Exception as e:  # noqa: BLE001
            logger.error("Combined report LLM generation failed: %s", e, exc_info=True)
            html_body = self._fallback_html(start_date, end_date, items)

        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Combined Report</title></head><body>{html_body}</body></html>"
        return {
            "title": f"Combined Report {start_date} ~ {end_date}",
            "html": html,
        }

    def _build_prompt(
        self, start_date: str, end_date: str, items: List[Dict[str, Any]]
    ) -> str:
        """
        한국어 최종 출력, HTML만 반환하도록 강제하는 프롬프트.
        """
        items_json = json.dumps(items, ensure_ascii=False, indent=2)
        return f"""
당신은 규제/리포트 문서를 요약하는 전문가이다.
아래 기간에 대해 종합 리포트를 작성하라. 최종 출력은 반드시 HTML 본문만 한글로 작성하고, 불필요한 설명/머리말은 넣지 마라.

[기간]
- 시작일: {start_date}
- 종료일: {end_date}

[입력 데이터(JSON)]
{items_json}

[작성 지침]
- HTML 본문(body)만 생성 (doctype/head/body 중 body 내용만 생성)
- 한국어로 작성
- 섹션 순서 예시:
  1) Executive Summary (간단 bullet)
  2) 주요 변경 사항 (bullet)
  3) 영향/리스크 (bullet)
  4) 대응 전략 (bullet)
  5) 참고/원문 링크 (bullet, URL 있으면 사용)
- 테이블/리스트는 기본 HTML 태그만 사용(스타일 불필요).
- 전체 출력은 HTML 태그만 포함하고 그 외 텍스트나 설명 금지.
"""

    async def _call_llm(self, prompt: str) -> str:
        response = await self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            stream=False,
        )
        return response.output_text

    def _fallback_html(
        self, start_date: str, end_date: str, items: List[Dict[str, Any]]
    ) -> str:
        return f"""
<h1>Combined Report {start_date} ~ {end_date}</h1>
<p>LLM 생성에 실패했습니다. 아래 데이터로 수동 검토하십시오.</p>
<pre>{json.dumps(items[:10], ensure_ascii=False, indent=2)}</pre>
"""
