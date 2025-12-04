"""
PDF 언어 감지 모듈

1) PDF 샘플 페이지에서 텍스트 추출
   - 먼저 pdfplumber로 텍스트 추출 시도
   - 텍스트 길이가 충분하면 → 텍스트 PDF로 판단
   - 텍스트가 거의 없으면 → 스캔 PDF로 판단하여 OCR 수행 (pypdfium2 + pytesseract)

2) 최종 확보한 텍스트를 get_language_detector()로 언어 감지

요약:
- 텍스트 PDF  → pdfplumber 사용
- 스캔 PDF     → OCR 사용
- 언어 감지     → lightweight detector.detect_language()
"""

from pathlib import Path
from typing import Dict, List, Any
import logging

import pdfplumber
import pypdfium2 as pdfium
import pytesseract

from .cleaner import get_language_detector

logger = logging.getLogger(__name__)


class PDFLanguageDetector:
    """텍스트 PDF vs 스캔 PDF 자동 판별 + OCR fallback 기반 언어 감지"""

    def __init__(self):
        self.language_detector = get_language_detector()

    # ---------------------------
    # 페이지 샘플링
    # ---------------------------
    def get_sample_pages(self, total_pages: int) -> List[int]:
        """
        중간 3장 샘플링 (기존 로직 유지)
        """
        if total_pages >= 5:
            mid = total_pages // 2
            return [mid - 1, mid, mid + 1]
        elif total_pages == 4:
            return [1, 2, 3]
        elif total_pages == 3:
            return [0, 1, 2]
        else:
            return list(range(total_pages))

    # ---------------------------
    # 텍스트 PDF 추출 시도 (pdfplumber)
    # ---------------------------
    def extract_text_pdfplumber(self, pdf_path: str, sample_pages: List[int]) -> str:
        """
        pdfplumber로 텍스트 추출 (텍스트 PDF에만 성공)
        """
        extracted_texts = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total = len(pdf.pages)
                for idx in sample_pages:
                    if idx < total:
                        page = pdf.pages[idx]
                        text = page.extract_text() or ""
                        if text.strip():
                            extracted_texts.append(text)
        except Exception as e:
            logger.error(f"pdfplumber 텍스트 추출 실패: {e}")
            return ""

        return "\n".join(extracted_texts)

    # ---------------------------
    # 스캔 PDF OCR 추출
    # ---------------------------
    def extract_text_ocr(self, pdf_path: str, sample_pages: List[int], dpi: int = 200) -> str:
        """
        스캔 PDF에서 OCR 수행 (pypdfium2 + pytesseract)
        """
        extracted_texts = []
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            total = len(pdf)

            for idx in sample_pages:
                if idx < total:
                    page = pdf[idx]
                    pil_img = page.render(scale=dpi / 72).to_pil()
                    text = pytesseract.image_to_string(pil_img)
                    if text.strip():
                        extracted_texts.append(text)

        except Exception as e:
            logger.error(f"OCR 추출 실패: {e}")
            return ""

        return "\n".join(extracted_texts)

    # ---------------------------
    # 텍스트 vs 스캔 자동 판별 → 텍스트 길이 threshold 기반
    # ---------------------------
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        1) pdfplumber로 텍스트 먼저 시도
        2) 텍스트가 너무 적으면 (스캔 PDF로 판단)
        3) OCR fallback
        """
        try:
            # 먼저 전체 페이지 수 확인
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

        except Exception as e:
            return {
                "success": False,
                "error": f"PDF 열기 실패: {e}",
                "total_pages": 0,
                "sample_pages": [],
                "text": ""
            }

        if total_pages == 0:
            return {
                "success": False,
                "error": "빈 PDF",
                "total_pages": 0,
                "sample_pages": [],
                "text": ""
            }

        sample_pages = self.get_sample_pages(total_pages)

        # 1) 텍스트 PDF 시도
        text = self.extract_text_pdfplumber(pdf_path, sample_pages)
        text_len = len(text.strip())

        logger.info(f"pdfplumber 텍스트 길이: {text_len}")

        # 2) 텍스트가 충분하면 텍스트 PDF로 판단 → OCR 안함
        if text_len >= 50:
            logger.info("텍스트 PDF로 판단 → OCR 생략")
            return {
                "success": True,
                "total_pages": total_pages,
                "sample_pages": sample_pages,
                "text": text,
                "text_length": text_len,
                "used_ocr": False
            }

        # 3) 텍스트 부족 → 스캔 PDF로 판단 → OCR fallback
        logger.info("텍스트 부족 → 스캔 PDF로 판단 → OCR 수행")
        ocr_text = self.extract_text_ocr(pdf_path, sample_pages)
        ocr_len = len(ocr_text.strip())

        return {
            "success": True,
            "total_pages": total_pages,
            "sample_pages": sample_pages,
            "text": ocr_text,
            "text_length": ocr_len,
            "used_ocr": True
        }

    # ---------------------------
    # 언어 감지
    # ---------------------------
    def detect_document_language(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 5:
            return {
                "language_code": "UNKNOWN",
                "language_name": "Unknown",
                "confidence": 0.0,
                "is_reliable": False
            }

        result = self.language_detector.detect_language(text)

        return {
            "language_code": result.get("language_code", "UNKNOWN"),
            "language_name": result.get("language_name", "Unknown"),
            "confidence": result.get("confidence", 0.0),
            "is_reliable": result.get("is_reliable", False)
        }

    # ---------------------------
    # 전체 프로세스
    # ---------------------------
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            return {
                "file_path": str(pdf_path),
                "success": False,
                "error": "File not found",
                "language_code": "ERROR",
                "language_name": "Error"
            }

        extraction_result = self.extract_text_from_pdf(str(pdf_path))

        if not extraction_result["success"]:
            return {
                "file_path": str(pdf_path),
                "success": False,
                "error": extraction_result["error"],
                "language_code": "ERROR",
                "language_name": "Error"
            }

        lang = self.detect_document_language(extraction_result["text"])

        return {
            "file_path": str(pdf_path),
            "success": True,
            "total_pages": extraction_result["total_pages"],
            "sample_pages": extraction_result["sample_pages"],
            "text_length": extraction_result["text_length"],
            "used_ocr": extraction_result["used_ocr"],
            "language_code": lang["language_code"],
            "language_name": lang["language_name"],
            "confidence": lang["confidence"],
            "is_reliable": lang["is_reliable"]
        }


# --------------------------------------------------
# 편의 함수
# --------------------------------------------------
def detect_pdf_language(pdf_path: str) -> Dict[str, Any]:
    detector = PDFLanguageDetector()
    return detector.process_pdf(pdf_path)
