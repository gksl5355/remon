from __future__ import annotations

import logging
from typing import Any, Dict, List
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from app.ai_pipeline.tools.llm_translator import LLMTranslator

logger = logging.getLogger(__name__)


class TranslationService:
    """
    규제 문서 전용 번역 + PDF 생성 서비스

    ⚠️ 중요 전제
    - 입력은 "단일 Markdown 문서"여야 한다
    - JSON / chunk / page metadata는 여기서 다루지 않는다
    """

    def __init__(self, translator: LLMTranslator | None = None):
        self.translator = translator or LLMTranslator()

        template_dir = Path(__file__).resolve().parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.jinja_env.globals["datetime"] = datetime

    # =========================
    # Public API
    # =========================
    async def translate_markdown_to_pdf(
        self,
        *,
        markdown_text: str,
        target_lang: str,
        title: str,
    ) -> Dict[str, Any]:
        """
        규제 Markdown → 번역 → PDF

        markdown_text:
          - vision_extraction_result[0].structure.markdown_content
        """

        if not markdown_text.strip():
            raise ValueError("markdown_text is empty")

        # 1️⃣ LLM 번역 (단일 문서)
        translated_markdown = await self._translate_single_markdown(
            markdown_text=markdown_text,
            target_lang=target_lang,
        )

        # 2️⃣ PDF 렌더링
        pdf_bytes = self._render_pdf(
            markdown_text=translated_markdown,
            title=title,
        )

        # 3️⃣ 로컬 저장
        pdf_path = self._save_pdf_local(
            pdf_bytes=pdf_bytes,
            title=title,
            lang=target_lang,
        )

        return {
            "pdf_path": str(pdf_path),
            "translated_markdown": translated_markdown,
        }

    # =========================
    # Translation
    # =========================
    async def _translate_single_markdown(
        self,
        *,
        markdown_text: str,
        target_lang: str,
    ) -> str:
        """
        Markdown 전체를 한 번에 번역한다.
        JSON 파싱 / 페이지 분할 / batch 개념 없음
        """

        pages = [
            {
                "page": 0,
                "markdown": markdown_text,
            }
        ]

        result = await self.translator.translate_markdown(
            pages=pages,
            target_lang=target_lang,
            glossary=None,
            save_dir=None,
        )

        # LLM 결과 안전 추출
        for batch in result.get("results", []):
            translated = batch.get("translated")

            # ✅ 가장 정상적인 케이스 (문자열)
            if isinstance(translated, str):
                return translated.strip()

            # ✅ JSON 배열 형태로 온 경우
            if isinstance(translated, list):
                md_parts: List[str] = []
                for item in translated:
                    if isinstance(item, dict) and item.get("markdown"):
                        md_parts.append(item["markdown"])
                if md_parts:
                    return "\n\n".join(md_parts).strip()

        raise RuntimeError("Failed to extract translated markdown from LLM result")

    # =========================
    # PDF Rendering
    # =========================
    def _render_pdf(self, *, markdown_text: str, title: str) -> bytes:
        """
        Markdown → HTML → PDF
        """
        html_body = markdown.markdown(
            markdown_text,
            extensions=[
                "tables",
                "sane_lists",
                "nl2br",
                "toc",
            ],
        )

        template = self.jinja_env.get_template("translated_markdown.html.j2")
        html = template.render(
            title=title,
            body=html_body,
        )

        return HTML(string=html, encoding="utf-8").write_pdf()

    # =========================
    # Save
    # =========================
    def _save_pdf_local(self, *, pdf_bytes: bytes, title: str, lang: str) -> Path:
        out_dir = Path("outputs/translations")
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_title = title.replace("/", "_").replace(" ", "_")
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        path = out_dir / f"{safe_title}_{lang}_{ts}.pdf"
        path.write_bytes(pdf_bytes)

        logger.info("Translated PDF saved to %s", path)
        return path
