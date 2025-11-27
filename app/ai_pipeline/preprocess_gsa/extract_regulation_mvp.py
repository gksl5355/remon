"""
module: extract_regulation_mvp.py
description: PDF를 페이지 이미지로 렌더링하고, 멀티모달 LLM으로 규제 JSON을 추출하는 MVP 파이프라인
author: ChatGPT
dependencies:
  - pymupdf
  - python-dotenv
  - openai (openai-python SDK)
env:
  - OPENAI_API_KEY (필수, .env 또는 환경변수)
"""

import os
import re
import json
import base64
from pathlib import Path

from dotenv import load_dotenv
import fitz  # PyMuPDF
from openai import OpenAI


# ---------------------------------------------------------
# 0. .env 자동 로딩 + API 키 체크
# ---------------------------------------------------------
load_dotenv()  # 프로젝트 루트에 있는 .env 로딩

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY가 설정되지 않았습니다.\n"
        "1) 프로젝트 루트에 .env 파일을 만들고\n"
        "   OPENAI_API_KEY=sk-... 형태로 추가하거나,\n"
        "2) 터미널에서 export OPENAI_API_KEY=sk-... 로 설정한 후 실행하세요."
    )

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------
# 1. PDF → 페이지별 이미지 렌더링
# ---------------------------------------------------------
def render_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    image_format: str = "png",
) -> list[str]:
    """
    PDF 파일을 페이지별 이미지로 렌더링하고, 저장된 이미지 경로 리스트를 반환한다.

    Args:
        pdf_path: 렌더링할 PDF 파일 경로
        output_dir: 이미지가 저장될 디렉터리 (없으면 자동 생성)
        dpi: 렌더링 해상도 (기본 200, 300 이상이면 꽤 선명)
        image_format: "png", "jpg" 등

    Returns:
        저장된 이미지 파일 경로(str) 리스트 (페이지 순서대로)
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    saved_paths: list[str] = []

    # PyMuPDF 기본 해상도는 72dpi라서, dpi 비율만큼 확대
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


# ---------------------------------------------------------
# 2. 이미지 → base64 인코딩
# ---------------------------------------------------------
def encode_image_to_base64(image_path: str) -> str:
    """
    이미지 파일을 base64 문자열로 인코딩한다.
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------
# 3. LLM가 ```json 코드블록으로 감싼 경우 처리 유틸
# ---------------------------------------------------------
def _extract_json_from_markdown(content: str) -> str:
    """
    LLM이 ```json ... ``` 또는 ``` ... ``` 코드블록으로 감싼 경우
    껍데기를 제거하고 JSON 본문만 추출한다.
    코드블록이 없으면 원본 content를 그대로 반환한다.
    """
    content = content.strip()

    # ```json ... ``` 또는 ``` ... ``` 패턴 매칭
    fenced_match = re.search(r"```(?:json)?\s*(.*)```", content, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()

    return content


# ---------------------------------------------------------
# 4. 멀티모달 LLM에 규제 JSON 추출 요청
# ---------------------------------------------------------
LLM_SCHEMA_PROMPT = """
You are an expert regulatory analyst.

You will receive one or more page images from a regulatory document (e.g., Federal Register, statutes, notices).
From the content of these images, extract the regulatory requirements and return them ONLY in the following JSON schema:

{
  "doc_meta": {
    "jurisdiction": "",
    "agency": "",
    "title": "",
    "publication_date": ""
  },
  "requirements": [
    {
      "requirement_type": "",
      "legal_basis": [],
      "actor": "",
      "products": [],
      "obligation": "",
      "timeline": ""
    }
  ]
}

Field guidelines:
- jurisdiction: country or region name (e.g., "US", "EU"). If unknown, use an empty string "".
- agency: the main regulatory authority (e.g., "FDA", "California Department of Public Health").
- title: official title or heading of the document, if present.
- publication_date: the publication date in the document, in ISO format YYYY-MM-DD if clearly stated, otherwise "".

- requirements: an array of regulatory requirements extracted from the document.
  - requirement_type: short label such as "reporting", "testing", "labeling", "marketing", "registration", etc.
  - legal_basis: list of legal citations or sections (e.g., "FD&C Act 904(a)(3)", "Section 22977").
  - actor: who must comply (e.g., "manufacturer", "importer", "retailer", "licensee").
  - products: list of product types covered (e.g., "cigarettes", "smokeless tobacco", "e-cigarette liquids").
  - obligation: clear description of what must be done.
  - timeline: explicit deadlines or timing rules (e.g., "at least 90 days before marketing", "annually", "by August 26, 2025").

Rules:
- Use exact phrasing from the document when possible for obligation and legal_basis.
- If some fields are not explicitly stated, fill them with an empty string "" or an empty array [].
- DO NOT add any extra top-level fields or change the structure.
- The response MUST be valid JSON, no comments, no trailing commas, no explanations.
- The response MUST NOT be wrapped in markdown code fences (no ``` or ```json).
"""


def extract_regulation_json_from_images(image_base64_list: list[str]) -> dict:
    """
    멀티모달 LLM에 페이지 이미지를 전달하고, 규제 JSON을 추출한다.

    Args:
        image_base64_list: raw base64 문자열 리스트 (접두어 없이 "iVBORw0..." 형태라고 가정)

    Returns:
        규제 JSON(dict). JSON 파싱 실패 시 {"error": ..., "raw": ...} 형태 반환.
    """

    user_content: list[dict] = [{"type": "text", "text": LLM_SCHEMA_PROMPT}]

    for img_b64 in image_base64_list:
        if not img_b64.startswith("data:image"):
            img_url = f"data:image/png;base64,{img_b64}"
        else:
            img_url = img_b64

        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": img_url
            }
        })

    messages = [
        {
            "role": "system",
            "content": "You are an AI assistant that extracts structured regulatory requirements from document images."
        },
        {
            "role": "user",
            "content": user_content
        },
    ]

    completion = client.chat.completions.create(
        model="gpt-4o",  # 멀티모달 지원 모델
        messages=messages,
        max_tokens=4000,
        temperature=0.0,
    )

    content = completion.choices[0].message.content

    # 1) 코드블록 껍데기 제거
    json_str = _extract_json_from_markdown(content)

    try:
        result_json = json.loads(json_str)
    except Exception as e:
        result_json = {
            "error": f"Invalid JSON format returned by LLM: {e}",
            "raw": content,
            "parsed_candidate": json_str,
        }

    return result_json


# ---------------------------------------------------------
# 5. 실행 예시 (MVP 테스트용)
# ---------------------------------------------------------
if __name__ == "__main__":
    # ⚠️ 이 경로들은 프로젝트 루트 기준 상대 경로라고 가정
    pdf = "/Users/broccoli/Desktop/remon/app/ai_pipeline/preprocess_gsa/사용데이터/practice_pdf.pdf"      # 실제 PDF 파일 경로
    out_dir = "output/pdf_images"         # 이미지 저장 폴더

    print("▶ PDF → 페이지별 이미지 렌더링 중...")
    image_paths = render_pdf_to_images(pdf, out_dir, dpi=200)
    print(f"  - 총 {len(image_paths)}개 페이지 렌더링 완료")

    # MVP: 앞 2~3페이지만 멀티모달에 던져보기
    first_n = 3
    target_image_paths = image_paths[:first_n]
    print(f"▶ 첫 {len(target_image_paths)}개 페이지를 멀티모달 LLM에 전달합니다.")

    # base64 인코딩
    encoded_images = [encode_image_to_base64(p) for p in target_image_paths]

    print("▶ 멀티모달 LLM에 규제 JSON 추출 요청...")
    regulation_json = extract_regulation_json_from_images(encoded_images)

    print("▶ 결과 JSON:")
    print(json.dumps(regulation_json, indent=2, ensure_ascii=False))
