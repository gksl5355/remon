"""
번역 프롬프트 템플릿.

- JSON 구조/키/타입/순서 보존
- fenced block 내부만 번역
- 용어사전 강제 적용
- HTML/메타데이터 수정 금지
"""

from __future__ import annotations

import json
from typing import List, Dict, Any


def build_translation_prompt(pages: List[Dict[str, Any]], glossary: Dict[str, str]) -> str:
    glossary_block = (
        "\n[용어사전]\n" +
        "다음 용어는 반드시 해당 번역어로 치환해야 한다(강제 적용):\n" +
        "\n".join([f"- {k} → {v}" for k, v in glossary.items()]) + "\n"
        if glossary else "(용어사전 없음)\n"
    )

    pages_json = json.dumps(pages, ensure_ascii=False, indent=2)
    return f"""
당신은 법령/규제 전문 번역 모델이다.

아래 규칙을 반드시 지켜라:

========================================
[핵심 준수 규칙]
========================================
1. JSON 구조, key 이름, value 타입, 배열 순서 절대 변경 금지
2. text 필드의 Markdown fenced block(```) 내부만 번역
3. text 외 메타데이터(page 번호 등)는 절대 수정 금지
4. 요약/생략/의역 금지, 문단/번호/들여쓰기 유지
5. 원문 라인 수·목차 구조 동일 유지
6. 출력은 반드시 JSON 전체 구조로만 반환
7. JSON 밖의 어떠한 설명/문장도 출력 금지

========================================
[용어사전 규칙]
========================================
[용어사전]
(이번 번역에서는 용어사전을 사용하지 않는다.)

========================================
[번역 범위 규칙]
========================================
- text 필드는 항상 다음 형태:
    "text": "```
원문...
```"
- fenced block 내부만 번역, fenced block 자체는 유지
- fenced block 밖 문자열은 절대 수정 금지
- 표/리스트는 원본 구조 그대로 유지

========================================
[입력 JSON]
========================================
다음 JSON을 번역하라 (배치 내 페이지 순서를 유지):

{pages_json}
"""


def build_markdown_translation_prompt(
    pages: List[Dict[str, Any]], glossary: Dict[str, str]
) -> str:
    """
    English prompt (concise) to reduce mis-formatting.
    Output must be JSON array only: [{"page": int, "markdown": "<translated markdown>"}]
    """
    pages_json = json.dumps(pages, ensure_ascii=False, indent=2)
    return f"""
You are a professional legal/technical translator.

Return ONLY a JSON array (no extra text): [{{"page": <int>, "markdown": "<translated markdown>"}}, ...]

Rules:
- Translate all content into Korean.
- Keep page numbers exactly as provided in input.
- Preserve Markdown structure, order, and layout exactly (headings, lists, tables, links).
- Tables: keep Markdown table syntax, headers/rows order unchanged.
- Lists/numbering/indentation/line breaks unchanged.
- URLs: translate link text, keep URL as-is.
- No paraphrasing, no summarizing, no omissions.
- Translate only the text; do NOT change code fences or Markdown tokens.
- Glossary: none for this run.

Pages to translate (keep page order and page numbers):
{pages_json}
"""
