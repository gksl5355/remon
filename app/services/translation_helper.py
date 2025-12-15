# app/services/translation_helper.py

from pathlib import Path
from app.services.translation_service import TranslationService


async def generate_translation_pdf_local(
    markdown_text: str,
    lang: str,
    title: str,
) -> str:
    """
    번역 + PDF 생성 후 local pdf_path 반환
    """
    service = TranslationService()

    result = await service.translate_markdown_to_pdf(
        markdown_text=markdown_text,
        target_lang=lang,
        title=title,
    )

    return result["pdf_path"]
