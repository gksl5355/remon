"""
Translation service skeleton.

역할
- 규제 번역 트리거 (이미 번역이 있으면 재사용, force=True 시 재번역)
- 번역 메타 조회 (status/s3_key 등)
- 번역/저장 구현은 추후 실제 번역기 붙일 때 채움
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Any, Dict, List
from datetime import datetime
import json
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown
from weasyprint import HTML

from app.core.repositories.translation_repository import TranslationRepository
from app.ai_pipeline.tools.llm_translator import LLMTranslator
from app.utils.s3_client import S3Client

logger = logging.getLogger(__name__)


@dataclass
class TranslationJob:
    """번역 요청/조회 시 공통으로 반환할 메타 정보"""

    translation_id: Optional[int]
    version_id: int
    language: str
    status: str  # queued | running | done | failed | not_found
    s3_key: Optional[str] = None
    presigned_url: Optional[str] = None
    error: Optional[str] = None


class TranslationService:
    """
    번역 서비스 인터페이스.

    실제 LLM/번역기 호출, S3 업로드, DB 업데이트는 추후 구현한다.
    """

    def __init__(
        self,
        repo: TranslationRepository | None = None,
        translator: LLMTranslator | None = None,
        s3_client: Any | None = None,
    ):
        self.repo = repo or TranslationRepository()
        self.translator = translator or LLMTranslator()
        self.s3_client = s3_client or self._init_s3_client()
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.jinja_env.globals["datetime"] = datetime

    async def trigger_translation(
        self,
        version_id: int,
        target_lang: str,
        db: AsyncSession,
        glossary_id: Optional[str] = None,
        force: bool = False,
    ) -> TranslationJob:
        """
        번역을 요청한다.

        - 이미 완료된 번역이 있으면 그대로 반환 (force=False)
        - force=True면 재번역을 트리거할 수 있게 남겨둔다.
        """
        existing = await self.repo.get_by_version_and_language(
            db, version_id, target_lang
        )

        # 이미 번역이 있고 재사용 가능한 경우
        if existing and not force:
            return self._job_from_model(existing)

        # 없거나 force=True면 새 번역 실행 (현재는 placeholder)
        try:
            pages = await self._load_source_pages(db, version_id)
            glossary: Dict[str, str] = (
                self.translator.load_glossary(glossary_id) if glossary_id else {}
            )

            if not pages:
                raise ValueError("Source pages not loaded. Implement source loader.")

            translated = await self.translator.translate(
                pages=pages, target_lang=target_lang, glossary=glossary
            )
            translated_text = self._serialize_translation(translated)

            s3_key = self._upload_translation(translated_text, version_id, target_lang)

            saved = await self.repo.upsert_translation(
                db,
                version_id=version_id,
                language_code=target_lang,
                translated_text=translated_text,
                glossary_term_id=glossary_id,
                translation_status="done",
                s3_key=s3_key,
            )
            await db.commit()
            return self._job_from_model(saved, translated_text=translated_text)

        except Exception as e:  # noqa: BLE001
            logger.error("Translation failed: %s", e, exc_info=True)
            failed = await self.repo.upsert_translation(
                db,
                version_id=version_id,
                language_code=target_lang,
                translated_text=None,
                glossary_term_id=glossary_id,
                translation_status="failed",
            )
            await db.commit()
            return self._job_from_model(
                failed, status_override="failed", error=str(e)
            )

    async def get_translation(
        self,
        version_id: int,
        target_lang: str,
        db: AsyncSession,
    ) -> TranslationJob:
        """
        번역 메타만 조회한다. 실행은 하지 않는다.
        """
        existing = await self.repo.get_by_version_and_language(
            db, version_id, target_lang
        )
        if not existing:
            return TranslationJob(
                translation_id=None,
                version_id=version_id,
                language=target_lang,
                status="not_found",
                s3_key=None,
                presigned_url=None,
                error=None,
            )
        return self._job_from_model(existing)

    async def get_translation_by_id(
        self, translation_id: int, db: AsyncSession
    ) -> TranslationJob:
        existing = await self.repo.get_by_id(db, translation_id)
        if not existing:
            return TranslationJob(
                translation_id=None,
                version_id=-1,
                language="",
                status="not_found",
                s3_key=None,
                presigned_url=None,
                error=None,
            )
        return self._job_from_model(existing)

    async def get_translation_content(
        self, translation_id: int, db: AsyncSession
    ) -> Optional[str]:
        existing = await self.repo.get_by_id(db, translation_id)
        if not existing or not existing.translated_text:
            return None
        return existing.translated_text

    def _serialize_translation(self, translated: Any) -> str:
        """
        번역 결과를 문자열로 직렬화한다. 실제 구현에서는 JSON 검증/정렬을 넣을 수 있다.
        """
        try:
            return json.dumps(translated, ensure_ascii=False, indent=2)
        except Exception:  # noqa: BLE001
            return str(translated)

    def _upload_translation(
        self, translated_text: str, version_id: int, target_lang: str
    ) -> Optional[str]:
        """
        번역 결과를 임시 파일로 저장 후 S3에 업로드하고 key를 반환한다.
        s3_client가 없거나 실패 시 None 반환.
        """
        if not self.s3_client:
            logger.warning("S3 client not configured; skipping upload.")
            return None

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        s3_key = f"translations/{version_id}/{target_lang}/translation_{timestamp}.json"

        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(translated_text)
            self.s3_client.upload_json(str(tmp_path), s3_key=s3_key)
            tmp_path.unlink(missing_ok=True)
            return s3_key
        except Exception as e:  # noqa: BLE001
            logger.error("S3 upload failed: %s", e, exc_info=True)
            return None

    def render_translated_markdown_pdf(
        self, merged_markdown: str, title: str
    ) -> bytes:
        """번역된 Markdown을 HTML 템플릿으로 감싸 PDF 변환"""
        html_body = markdown.markdown(
            merged_markdown, extensions=["tables", "sane_lists", "nl2br"]
        )
        template = self.jinja_env.get_template("translated_markdown.html.j2")
        html = template.render(title=title, body=html_body)
        pdf_bytes = HTML(string=html, encoding="utf-8").write_pdf()
        return pdf_bytes

    def merge_markdown_batches(self, result: Dict[str, Any]) -> str:
        """
        번역 결과 JSON 배열에서 page 번호 순서대로 markdown을 합쳐 하나의 문서로 만든다.
        """
        sections: List[str] = []
        by_page: Dict[Any, List[str]] = {}
        for batch in result.get("results", []):
            translated = batch.get("translated")
            items = translated if isinstance(translated, list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                page = item.get("page")
                md = item.get("markdown")
                if md is None:
                    continue
                by_page.setdefault(page, []).append(md)
        if not by_page:
            return ""
        order = result.get("page_order") or sorted(
            p for p in by_page.keys() if p is not None
        )
        for page in order:
            if page not in by_page:
                continue
            header = f"## 페이지 {int(page)+1}" if isinstance(page, (int, float)) else "## 페이지"
            sections.append(header)
            sections.extend(by_page[page])
            sections.append("---")
        return "\n\n".join(sections)

    async def translate_markdown_to_pdf(
        self,
        pages: List[Dict[str, Any]],
        target_lang: str,
        batch_pages: int = 1,
        glossary: Optional[Dict[str, str]] = None,
        version_id: Optional[int] = None,
        title: str = "번역본",
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Markdown 페이지 리스트를 번역 → 병합 → PDF 렌더 → (옵션) S3 업로드까지 수행.
        DB 세션이 주어지면 translation row도 업데이트한다.
        """
        # LLM 번역
        self.translator.batch_pages = batch_pages
        result = await self.translator.translate_markdown(
            pages=pages,
            target_lang=target_lang,
            glossary=glossary,
            save_dir=None,
        )

        # 병합
        merged_md = self.merge_markdown_batches(result)

        # PDF 렌더
        pdf_bytes = self.render_translated_markdown_pdf(
            merged_markdown=merged_md,
            title=title,
        )

        s3_key = None
        if self.s3_client and version_id:
            s3_key = self._upload_pdf(pdf_bytes, version_id, target_lang)

        # DB 업데이트
        if db and version_id:
            saved = await self.repo.upsert_translation(
                db,
                version_id=version_id,
                language_code=target_lang,
                translated_text=merged_md,
                glossary_term_id=None,
                translation_status="done",
                s3_key=s3_key,
            )
            await db.commit()

        return {
            "pdf_bytes": pdf_bytes,
            "merged_markdown": merged_md,
            "s3_key": s3_key,
            "llm_result": result,
        }

    def _job_from_model(
        self,
        model: Any,
        status_override: Optional[str] = None,
        translated_text: Optional[str] = None,
        error: Optional[str] = None,
    ) -> TranslationJob:
        """
        RegulationTranslation 모델을 TranslationJob으로 변환한다.

        규제 테이블에 s3_key 컬럼이 없으므로, 실제 구현 시 translated_text를
        바로 담거나 별도 컬럼을 추가해야 한다.
        """
        # status 컬럼이 없거나 비어 있는 경우 done으로 간주
        status = status_override or getattr(model, "translation_status", None) or "done"
        presigned_url = None
        s3_key = getattr(model, "s3_key", None)
        if self.s3_client and s3_key:
            try:
                presigned_url = self.s3_client.generate_presigned_url(s3_key)
            except Exception:  # noqa: BLE001
                presigned_url = None

        return TranslationJob(
            translation_id=model.translation_id,
            version_id=model.regulation_version_id,
            language=model.language_code,
            status=status,
            s3_key=s3_key,
            presigned_url=presigned_url,
            error=error,
        )

    def _init_s3_client(self) -> Optional[S3Client]:
        """환경 변수 기반 S3 클라이언트 초기화. 실패 시 None 반환."""
        try:
            return S3Client()
        except Exception as e:  # noqa: BLE001
            logger.warning("S3 client init failed: %s", e)
            return None

    async def _load_source_pages(
        self, db: AsyncSession, version_id: int
    ) -> List[Dict[str, Any]]:
        """
        regulation_chunks.content_jsonb를 version_id 기준으로 로드한다.

        규제 원문이 jsonb로 저장되어 있다고 가정.
        """
        query = text(
            """
            SELECT content_jsonb
            FROM regulation_chunks
            WHERE version_id = :version_id
            ORDER BY section_idx, chunk_id
            """
        )
        result = await db.execute(query, {"version_id": version_id})
        rows = result.mappings().all()
        pages: List[Dict[str, Any]] = []
        for row in rows:
            content = row.get("content_jsonb")
            if content is not None:
                pages.append(content)
        return pages
