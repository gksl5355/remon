"""
module: report_service.py
description: 리포트 생성, 조회 및 관련 비즈니스 로직을 처리하는 서비스 계층
author: 조영우
created: 2025-11-10
updated: 2025-11-20
dependencies:
    - sqlalchemy.ext.asyncio
    - core.repositories.report_repository
"""

import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.report_repository import ReportSummaryRepository, ReportRepository
from app.ai_pipeline.tools.combined_report_generator import CombinedReportGenerator
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from pathlib import Path
from app.utils.s3_client import S3Client
from datetime import datetime
import markdown

logger = logging.getLogger(__name__)


class ReportService:
    """리포트 관련 비즈니스 로직을 처리하는 서비스 클래스"""
    
    def __init__(self):
        self.repo = ReportSummaryRepository()
        self.report_repo = ReportRepository()
        self.combined_generator = CombinedReportGenerator()
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.jinja_env.globals["datetime"] = datetime
        try:
            self.s3_client = S3Client()
        except Exception:
            self.s3_client = None

    
    async def get_all_summaries(self, db: AsyncSession) -> dict:
        """
        모든 리포트 요약 목록을 조회한다.
        
        Returns:
            dict: {summary_id: {title, last_updated, sections}}
        """
        logger.info("Fetching all summaries")
        
        summaries = await self.repo.get_all(db)
        result = {}
        
        for summary in summaries:
            result[summary.summary_id] = {
                "title": summary.summary_text[0].get("title", "제목 없음") if summary.summary_text else "제목 없음",
                "last_updated": summary.created_at.strftime("%Y-%m-%d") if summary.created_at else "",
                "sections": summary.summary_text
            }
        
        return result
    
    
    async def update_report(self, db: AsyncSession, summary_id: int, sections: list) -> dict | None:
        """
        리포트 요약의 sections를 업데이트한다.
        
        Returns:
            dict | None: {title, last_updated, sections}
        """
        logger.info(f"Updating summary: summary_id={summary_id}")
        
        summary = await self.repo.get_by_summary_id(db, summary_id)
        
        if not summary:
            return None
        
        await self.repo.update(db, summary_id, summary_text=sections)
        await db.commit()
        
        from datetime import date
        return {
            "title": sections[0].get("title", "제목 없음") if sections else "제목 없음",
            "last_updated": str(date.today()),
            "sections": sections
        }
    
    async def delete_report(self, db: AsyncSession, summary_id: int) -> bool:
        """
        리포트 요약을 삭제한다.
        
        Returns:
            bool: 삭제 성공 여부
        """
        logger.info(f"Deleting summary: summary_id={summary_id}")
        
        summary = await self.repo.get_by_summary_id(db, summary_id)
        
        if not summary:
            return False
        
        await self.repo.delete(db, summary_id)
        await db.commit()
        
        return True
    
    async def get_report_detail(self, db: AsyncSession, summary_id: int) -> dict | None:
        """
        리포트 상세 정보를 조회한다 (프론트 형식).

        Args:
            db (AsyncSession): 데이터베이스 세션.
            summary_id (int): 규제 문서 ID.

        Returns:
            dict | None: 리포트 상세 정보 또는 None.
        """
        logger.info(f"Fetching report detail: summary_id={summary_id}")
        
        try:
            summary = await self.repo.get_by_summary_id(db, summary_id)
            
            if not summary:
                logger.warning(f"Report not found: summary_id={summary_id}")
                return None
            
            # summary_text는 JSONB (sections 배열)
            if summary.summary_text:
                return {
                    "regulation_id": summary_id,
                    "title": "",
                    "last_updated": summary.created_at.isoformat() if summary.created_at else None,
                    "sections": summary.summary_text  # 이미 배열 형식
                }
            
            # JSONB 데이터가 없으면 None 반환
            logger.warning(f"No summary data found for regulation_id={summary_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching report detail: {e}", exc_info=True)
            return None

    async def create_report(
        self,
        db: AsyncSession,
        regulation_id: int,
        report_type: str
    ) -> dict:
        """
        리포트 생성을 요청한다 (AI 파이프라인 트리거).

        Args:
            db (AsyncSession): 데이터베이스 세션.
            regulation_id (int): 규제 문서 ID.
            report_type (str): 리포트 타입 (summary/comprehensive).

        Returns:
            dict: 생성된 리포트 ID 및 상태.
        """
        logger.info(f"Creating report for regulation_id={regulation_id}, type={report_type}")
        
        async with db.begin():
            # TODO: AI1(고서아) - ai_service.generate_report() 호출
            pass
        
        return {"report_id": None, "status": "pending"}


    async def download_report(self, db: AsyncSession, report_id: int) -> Optional[bytes]:
        """
        리포트를 PDF/Excel 파일로 다운로드한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.
            report_id (int): 리포트 ID.

        Returns:
            bytes | None: 파일 바이너리 데이터 또는 None.
        """
        logger.info(f"Downloading report: report_id={report_id}")
        
        # 캐시된 PDF가 있는지 확인 (report.s3_key/pdf_updated_at vs summary.updated_at)
        report_obj = await db.get(self.report_repo.model, report_id)
        summary = await self.repo.get_by_summary_id(db, report_id)
        if not summary or not summary.summary_text:
            logger.warning("Report summary not found or empty: %s", report_id)
            return None
        # TODO: summary.updated_at 컬럼이 있다면 비교. 없으면 created_at 기준 사용
        summary_updated = getattr(summary, "created_at", None)
        report_s3_key = getattr(report_obj, "s3_key", None)
        report_pdf_updated_at = getattr(report_obj, "pdf_updated_at", None)
        cached_fresh = (
            report_obj
            and report_s3_key
            and report_pdf_updated_at
            and summary_updated
            and report_pdf_updated_at >= summary_updated
        )

        if cached_fresh and self.s3_client:
            try:
                presigned = self.s3_client.generate_presigned_url(report_s3_key)
                logger.info("Serving cached PDF from S3 for report_id=%s", report_id)
                return await self._download_s3(presigned)
            except Exception:
                logger.warning("Failed to fetch cached PDF; regenerating.", exc_info=True)

        # 렌더 후 S3 업로드
        html = self._render_summary_html(
            report_id=report_id,
            summary_text=summary.summary_text,
            last_updated=getattr(summary, "created_at", None),
        )
        pdf_bytes = self._html_to_pdf(html)
        if self.s3_client and report_obj:
            try:
                s3_key = self._upload_pdf(pdf_bytes, f"reports/{report_id}.pdf")
                updater = getattr(self.report_repo, "update_pdf_meta", None)
                if callable(updater):
                    await updater(db, report_id, s3_key)
                    await db.commit()
            except Exception:
                logger.warning("Failed to upload or update PDF metadata; continuing without S3 cache.", exc_info=True)
        return pdf_bytes

    async def download_combined_report(
        self, start_date: str, end_date: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """
        기간별 종합 리포트 HTML 생성 (LLM placeholder).
        """
        items: List[Dict[str, Any]] = []
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            summaries = await self.repo.get_by_date_range(
                db=db, start_dt=start_dt, end_dt=end_dt
            )
            for s in summaries:
                items.append(
                    {
                        "summary_id": s.summary_id,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "sections": s.summary_text,
                    }
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to load summaries for combined report: %s", e)

        try:
            generated = await self.combined_generator.generate(
                start_date=start_date,
                end_date=end_date,
                items=items,
            )
            html = generated.get("html", "")
        except Exception as e:  # noqa: BLE001
            logger.warning("Combined report generation failed: %s", e)
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Combined Report</title></head>
<body>
  <h1>Combined Report {start_date} ~ {end_date}</h1>
  <p>내용은 추후 실제 데이터로 교체 예정입니다.</p>
</body></html>"""

        pdf_bytes = self._html_to_pdf(html)
        s3_key = None
        if self.s3_client:
            s3_key = self._upload_pdf(
                pdf_bytes,
                f"reports/combined/combined_{start_date}_{end_date}.pdf",
            )
        return {
            "filename": f"combined_{start_date}_{end_date}.pdf",
            "content": pdf_bytes,
            "s3_key": s3_key,
        }

    def _render_summary_html(self, report_id: int, summary_text: Any, last_updated: Optional[datetime] = None) -> str:
        """
        summary_text를 Jinja 템플릿으로 HTML 렌더링.
        """
        raw_sections: List[Dict[str, Any]] = []
        if isinstance(summary_text, dict):
            for _, section in summary_text.items():
                if isinstance(section, dict):
                    raw_sections.append(section)
        elif isinstance(summary_text, list):
            for item in summary_text:
                if isinstance(item, dict):
                    raw_sections.append(item)

        def _find_section(keys: List[str]) -> Optional[Dict[str, Any]]:
            for s in raw_sections:
                title = s.get("title", "")
                sec_id = s.get("id", "")
                if any(k in title for k in keys) or sec_id in keys:
                    return s
            return None

        def _normalize_content(section: Dict[str, Any], default: str = "데이터가 없습니다.") -> List[str]:
            content = section.get("content")
            if content is None:
                return [default]
            if isinstance(content, list):
                return [str(c) for c in content if c is not None]
            return [str(content)]

        def _normalize_tables(section: Dict[str, Any]) -> List[Dict[str, Any]]:
            tables = section.get("tables") or []
            normalized = []
            for tbl in tables:
                headers = tbl.get("headers") or ["항목", "내용"]
                rows = tbl.get("rows") or [["데이터 없음", "-"]]
                normalized.append(
                    {
                        "product_name": tbl.get("product_name", ""),
                        "headers": headers,
                        "rows": rows,
                    }
                )
            if not normalized:
                normalized.append(
                    {
                        "product_name": "",
                        "headers": ["항목", "내용"],
                        "rows": [["데이터 없음", "-"]],
                    }
                )
            return normalized

        def _normalize_links(section: Dict[str, Any]) -> List[Dict[str, str]]:
            links = section.get("content") or []
            normalized = []
            for link in links:
                if isinstance(link, dict):
                    normalized.append(
                        {
                            "url": link.get("url") or link.get("link") or "#",
                            "text": link.get("text") or link.get("title") or link.get("url") or "링크",
                        }
                    )
                else:
                    normalized.append({"url": str(link), "text": str(link)})
            return normalized

        ordered_sections: List[Dict[str, Any]] = []
        overall = _find_section(["overall", "종합 요약"])
        if overall:
            ordered_sections.append(
                {"title": "0. 종합 요약", "type": "list", "content": _normalize_content(overall)}
            )

        change = _find_section(["규제 변경 요약", "change"])
        if change:
            ordered_sections.append(
                {"title": "1. 규제 변경 요약", "type": "list", "content": _normalize_content(change)}
            )

        products = _find_section(["제품 분석", "products"])
        if products:
            ordered_sections.append(
                {
                    "title": "2. 영향받는 제품 목록",
                    "type": "nested_tables",
                    "tables": _normalize_tables(products),
                }
            )

        analysis = _find_section(["변경 사항", "major", "changes"])
        if analysis:
            ordered_sections.append(
                {"title": "3. 주요 변경 사항 해석", "type": "list", "content": _normalize_content(analysis)}
            )

        strategy = _find_section(["대응 전략", "strategy"])
        if strategy:
            ordered_sections.append(
                {"title": "4. 대응 전략", "type": "list", "content": _normalize_content(strategy)}
            )

        impact = _find_section(["영향 평가", "impact"])
        if impact:
            ordered_sections.append(
                {
                    "title": "5. 영향 평가 근거",
                    "type": "paragraph",
                    "content": _normalize_content(impact),
                }
            )

        references = _find_section(["참고", "references"])
        if references:
            ordered_sections.append(
                {"title": "6. 참고 및 원문 링크", "type": "links", "content": _normalize_links(references)}
            )

        if not ordered_sections:
            ordered_sections = raw_sections

        context = {
            "title": f"Report #{report_id}",
            "last_updated": last_updated,
            "sections": ordered_sections,
        }
        template = self.jinja_env.get_template("report.html.j2")
        return template.render(**context)

    def _html_to_pdf(self, html: str) -> bytes:
        """weasyprint로 HTML을 PDF로 변환"""
        pdf = HTML(string=html, encoding="utf-8").write_pdf()
        return pdf

    def _upload_pdf(self, pdf_bytes: bytes, s3_key: str) -> Optional[str]:
        if not self.s3_client:
            return None
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            # boto3 직접 호출 (S3Client는 json 전용 업로드만 있었음)
            self.s3_client.s3.upload_file(tmp_path, self.s3_client.bucket_arn, s3_key)
            return s3_key
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _download_s3(self, presigned_url: str) -> Optional[bytes]:
        """
        presigned URL로부터 파일을 다운로드.
        """
        import requests

        resp = requests.get(presigned_url, timeout=30)
        if resp.status_code == 200:
            return resp.content
        return None
