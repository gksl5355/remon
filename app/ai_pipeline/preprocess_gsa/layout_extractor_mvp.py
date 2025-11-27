"""
module: layout_extractor_mvp.py
description:
  PDF를 페이지별 이미지로 렌더링하고,
  각 페이지에서 문단(blocks) / 각주(footnotes)를 멀티모달 LLM으로 추출하는 MVP.
  이후 cross-page 블록 병합 용도의 중간 레이아웃 JSON을 생성한다.

author: ChatGPT
"""

import os
import re
import json
import base64
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
import fitz  # PyMuPDF
from openai import OpenAI

# ---------------------------------------------------------
# 0. .env 로딩 + OpenAI 클라이언트
# ---------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 환경변수에 설정하세요."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
# 1. PDF → 페이지별 이미지 렌더링 (재사용)
# ---------------------------------------------------------
def render_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    image_format: str = "png",
) -> List[str]:
    """
    PDF 파일을 페이지별 이미지로 렌더링하고, 저장된 이미지 경로 리스트를 반환한다.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    saved_paths: List[str] = []

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        filename = f"{pdf_path.stem}_p{page_index + 1:03d}.{image_format}"
        out_path = output_dir / filename

        pix.save(out_path.as_posix())
        saved_paths.append(str(out_path))

    doc.close()
    return saved_paths


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------
# 2. 코드블록(JSON) 껍데기 제거 유틸
# ---------------------------------------------------------
def _extract_json_from_markdown(content: str) -> str:
    """
    LLM이 ```json ... ``` 형태로 감싼 경우 껍데기를 제거하고 JSON 본문만 반환.
    """
    content = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*)```", content, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()
    return content


# ---------------------------------------------------------
# 3. 레이아웃 JSON 스키마 & 프롬프트
# ---------------------------------------------------------
LAYOUT_PROMPT = """
You are an expert in document layout analysis.

You will receive a single page image from a regulatory PDF (e.g., Federal Register, statutes).
From this page, extract the text into logical blocks and footnotes using the following JSON schema:

{
  "page_num": 0,
  "blocks": [
    {
      "id": "",
      "type": "heading | paragraph | list_item | other",
      "text": ""
    }
  ],
  "footnotes": [
    {
      "marker": "",
      "text": ""
    }
  ]
}

Guidelines:
- "blocks" should represent the main reading order on this page.
  - "heading": section titles like "SUMMARY", "DATES", "SUPPLEMENTARY INFORMATION".
  - "paragraph": normal text paragraphs.
  - "list_item": bullet or numbered items.
  - "other": anything that doesn't clearly fit above (e.g., header/footer).
- Do NOT include footnote text in "blocks". Footnotes must go into "footnotes".
- "footnotes":
  - Usually in smaller font near the bottom of the page.
  - Often start with a marker like "1.", "2.", "†", "*", etc.
  - Put only the footnote text into "text", without duplicating the main paragraph.

Rules:
- Keep the text of each block as continuous readable text (line breaks removed where appropriate).
- Maintain the natural reading order from top to bottom, left to right.
- Do NOT add extra top-level fields or change the schema.
- The response MUST be strict JSON, no markdown, no comments, no explanation.
"""


def extract_layout_for_page(image_base64: str, page_num: int) -> Dict[str, Any]:
    """
    단일 페이지 이미지(base64)를 받아 해당 페이지의 레이아웃 JSON을 추출한다.
    """
    if not image_base64.startswith("data:image"):
        image_url = f"data:image/png;base64,{image_base64}"
    else:
        image_url = image_base64

    user_content = [
        {"type": "text", "text": LAYOUT_PROMPT},
        {
            "type": "image_url",
            "image_url": {"url": image_url},
        },
    ]

    messages = [
        {
            "role": "system",
            "content": "You extract structured layout (blocks, footnotes) from document page images."
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    completion = client.chat.completions.create(
        model="gpt-4o",  # 멀티모달
        messages=messages,
        max_tokens=3000,
        temperature=0.0,
    )

    content = completion.choices[0].message.content
    json_str = _extract_json_from_markdown(content)

    try:
        data = json.loads(json_str)
    except Exception as e:
        return {
            "page_num": page_num,
            "error": f"JSON parse error: {e}",
            "raw": content,
        }

    # page_num이 0으로 나오면 실제 페이지 번호로 덮어쓰기
    if isinstance(data, dict):
        data.setdefault("page_num", page_num)
    return data


# ---------------------------------------------------------
# 4. cross-page 블록 병합 (간단 heuristic)
# ---------------------------------------------------------
END_PUNCT = (".", "?", "!", ":", ";")

def _should_merge(prev_text: str, next_text: str) -> bool:
    """
    아주 간단한 heuristic:
    - 이전 블록이 문장부호로 끝나지 않고
    - 다음 블록이 소문자나 접속사로 시작하면 이어진 문단으로 판단.
    """
    if not prev_text:
        return False
    prev_text = prev_text.rstrip()
    if prev_text.endswith(END_PUNCT):
        return False

    next_text = next_text.lstrip()
    if not next_text:
        return False

    # 소문자 시작 or 접속사/전치사 느낌 단어로 시작하면 이어진 문장일 가능성 ↑
    first_token = next_text.split()[0]
    if first_token[0].islower():
        return True
    if first_token.lower() in {"and", "or", "but", "however", "therefore"}:
        return True
    return False


def merge_blocks_across_pages(layout_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    페이지별 레이아웃 JSON 리스트에서 blocks를 전부 펼친 뒤,
    간단한 규칙으로 cross-page 이어지는 문단을 병합한다.

    Returns:
        merged_blocks: [{"id": "...", "page_start": 1, "page_end": 2, "type": "...", "text": "..."}]
    """
    # page_num 기준으로 정렬
    sorted_pages = sorted(
        [p for p in layout_pages if isinstance(p, dict)],
        key=lambda x: x.get("page_num", 0),
    )

    merged_blocks: List[Dict[str, Any]] = []
    prev_block: Dict[str, Any] | None = None

    for page in sorted_pages:
        page_num = page.get("page_num", 0)
        blocks = page.get("blocks") or []

        for idx, block in enumerate(blocks):
            text = (block.get("text") or "").strip()
            btype = block.get("type") or "paragraph"
            bid = block.get("id") or f"p{page_num}_{idx:03d}"

            if not text:
                continue

            if prev_block is None:
                prev_block = {
                    "id": bid,
                    "type": btype,
                    "text": text,
                    "page_start": page_num,
                    "page_end": page_num,
                }
                continue

            # 현재 블록과 이전 블록을 병합할지 판단
            if _should_merge(prev_block["text"], text):
                # 병합
                prev_block["text"] = prev_block["text"].rstrip() + " " + text.lstrip()
                prev_block["page_end"] = page_num
            else:
                # 이전 블록 확정
                merged_blocks.append(prev_block)
                prev_block = {
                    "id": bid,
                    "type": btype,
                    "text": text,
                    "page_start": page_num,
                    "page_end": page_num,
                }

    if prev_block is not None:
        merged_blocks.append(prev_block)

    return merged_blocks


# ---------------------------------------------------------
# 5. 실행 예시 (MVP)
# ---------------------------------------------------------
if __name__ == "__main__":
    PDF_PATH = "/Users/broccoli/Desktop/remon/app/ai_pipeline/preprocess_gsa/사용데이터/practice_pdf.pdf"
    OUT_DIR = "output/pdf_images"

    print("▶ PDF → 페이지별 이미지 렌더링 중...")
    image_paths = render_pdf_to_images(PDF_PATH, OUT_DIR, dpi=200)
    print(f"  - 총 {len(image_paths)}개 페이지 렌더링 완료")

    # 테스트용: 앞 3페이지만 레이아웃 추출
    target_paths = image_paths[:3]
    layout_pages: List[Dict[str, Any]] = []

    for i, img_path in enumerate(target_paths, start=1):
        print(f"▶ 페이지 {i} 레이아웃 추출 중...")
        b64 = encode_image_to_base64(img_path)
        layout = extract_layout_for_page(b64, page_num=i)
        layout_pages.append(layout)

    print("▶ 페이지별 레이아웃 JSON:")
    print(json.dumps(layout_pages, indent=2, ensure_ascii=False))

    print("▶ cross-page 블록 병합 결과:")
    merged = merge_blocks_across_pages(layout_pages)
    print(json.dumps(merged, indent=2, ensure_ascii=False))
