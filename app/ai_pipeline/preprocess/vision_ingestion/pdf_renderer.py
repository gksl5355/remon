"""
module: pdf_renderer.py
description: PDF를 고해상도 이미지로 렌더링 (pypdfium2 사용)
author: AI Agent
created: 2025-01-14
dependencies: pypdfium2
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class PDFRenderer:
    """PDF 페이지를 이미지로 렌더링."""
    
    def __init__(self, dpi: int = 300):
        self.dpi = dpi
    
    def render_page_with_dpi(self, pdf_path: str, page_idx: int, dpi: int) -> Dict[str, Any]:
        """
        단일 페이지를 지정된 DPI로 렌더링.
        
        Args:
            pdf_path: PDF 파일 경로
            page_idx: 페이지 인덱스 (0-based)
            dpi: 렌더링 DPI
            
        Returns:
            Dict: {"page_num": 1, "image_base64": "...", "width": 2480, "height": 3508, "dpi": 300}
        """
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise ImportError("pypdfium2가 설치되지 않았습니다: pip install pypdfium2")
        
        pdf = pdfium.PdfDocument(pdf_path)
        page = pdf[page_idx]
        
        # 이미지 렌더링
        pil_image = page.render(scale=dpi/72).to_pil()
        
        # Base64 인코딩
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        pdf.close()
        
        return {
            "page_num": page_idx + 1,
            "image_base64": image_base64,
            "width": pil_image.width,
            "height": pil_image.height,
            "dpi": dpi
        }
        
    def render_pages(self, pdf_path: str, page_range: tuple[int, int] | None = None) -> List[Dict[str, Any]]:
        """
        PDF 페이지를 이미지로 렌더링.
        
        Args:
            pdf_path: PDF 파일 경로
            page_range: (start, end) 페이지 범위. None이면 전체
            
        Returns:
            List[Dict]: [{"page_num": 1, "image_base64": "...", "width": 2480, "height": 3508}]
        """
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise ImportError("pypdfium2가 설치되지 않았습니다: pip install pypdfium2")
        
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        
        start, end = page_range if page_range else (0, total_pages)
        end = min(end, total_pages)
        
        logger.info(f"PDF 렌더링 시작: {Path(pdf_path).name}, 페이지 {start+1}-{end} / {total_pages}")
        
        rendered_pages = []
        
        for page_idx in range(start, end):
            page = pdf[page_idx]
            
            # 이미지 렌더링
            pil_image = page.render(scale=self.dpi/72).to_pil()
            
            # Base64 인코딩
            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            rendered_pages.append({
                "page_num": page_idx + 1,
                "image_base64": image_base64,
                "width": pil_image.width,
                "height": pil_image.height
            })
            
            logger.debug(f"  페이지 {page_idx+1} 렌더링 완료: {pil_image.width}x{pil_image.height}")
        
        pdf.close()
        logger.info(f"PDF 렌더링 완료: {len(rendered_pages)}개 페이지")
        
        return rendered_pages
