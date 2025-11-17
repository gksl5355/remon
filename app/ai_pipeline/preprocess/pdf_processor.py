"""
module: pdf_processor.py
description: PDF 파일 처리 (로드, 텍스트 추출, 페이지 관리)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger
    - pypdf (또는 pdfplumber, pdf2image)
    - typing, re
"""

from typing import List, Dict, Optional, Tuple, Any
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# PDF 라이브러리들 (우선순위: PyMuPDF > pdfplumber > pypdf)
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("⚠️ PyMuPDF 미설치. pip install pymupdf 권장 (속도 최적화)")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("⚠️ pdfplumber 미설치. pip install pdfplumber 필요")

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False
    logger.warning("⚠️ pypdf 미설치. pip install pypdf 필요")


class PDFProcessor:
    """
    PDF 파일을 처리하고 텍스트 + 테이블 정보를 추출하는 클래스.
    
    역할:
    - PDF 파일 로드
    - 페이지별 텍스트 추출
    - 테이블 영역 감지 (좌표 정보 포함)
    - 메타데이터 추출 (제목, 작성일, 페이지 수 등)
    - 텍스트 정규화 (불필요한 공백, 특수문자 처리)
    
    특징:
    - 다양한 PDF 라이브러리 지원 (pypdf, pdfplumber)
    - 페이지 구조 유지 (문서 흐름 보존)
    - 테이블 좌표 정보 반환 (table_detector.py와 연동)
    """
    
    def __init__(self, prefer_library: str = "pymupdf"):
        """
        PDF 프로세서 초기화.
        
        Args:
            prefer_library (str): 선호 라이브러리. 'pymupdf', 'pdfplumber', 'pypdf'. 기본값: 'pymupdf'
        """
        self.prefer_library = prefer_library
        logger.info(f"✅ PDFProcessor 초기화: prefer_library={prefer_library}")
    
    def load_and_extract(
        self, pdf_path: str, extract_tables: bool = True, max_pages: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        PDF 파일을 로드하고 텍스트 + 테이블을 추출합니다.
        
        Args:
            pdf_path (str): PDF 파일 경로
            extract_tables (bool): 테이블 추출 여부. 기본값: True
            max_pages (Optional[int]): 최대 추출 페이지 수. None이면 전체. 기본값: None
        
        Returns:
            Dict[str, Any]: {
                "status": "success" | "error",
                "metadata": {
                    "num_pages": 총 페이지 수,
                    "title": PDF 제목,
                    "author": 작성자,
                    "creation_date": 생성 날짜,
                },
                "pages": [
                    {
                        "page_num": 1,
                        "text": "페이지 텍스트",
                        "tables": [
                            {"bbox": [x1, y1, x2, y2], "content": "테이블 내용"}
                        ] if extract_tables else [],
                    },
                    ...
                ],
                "full_text": "전체 텍스트 (페이지 구분자 포함)",
                "error": 에러 메시지 (error 발생 시)
            }
        
        Raises:
            FileNotFoundError: PDF 파일이 없을 경우
            ValueError: 지원하지 않는 형식
        """
        pdf_file = Path(pdf_path)
        
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF 파일 없음: {pdf_path}")
        
        if pdf_file.suffix.lower() != ".pdf":
            raise ValueError(f"PDF 파일이 아님: {pdf_file.suffix}")
        
        try:
            if HAS_PYMUPDF and self.prefer_library == "pymupdf":
                return self._extract_with_pymupdf(pdf_file, extract_tables, max_pages)
            elif HAS_PDFPLUMBER and self.prefer_library == "pdfplumber":
                return self._extract_with_pdfplumber(pdf_file, extract_tables, max_pages)
            elif HAS_PDFPLUMBER:
                return self._extract_with_pdfplumber(pdf_file, extract_tables, max_pages)
            elif HAS_PYPDF:
                return self._extract_with_pypdf(pdf_file, extract_tables, max_pages)
            else:
                raise RuntimeError("PDF 라이브러리 미설치 (pymupdf, pdfplumber, pypdf 중 하나 필요)")
        
        except Exception as e:
            logger.error(f"PDF 추출 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    def _extract_with_pymupdf(
        self, pdf_path: Path, extract_tables: bool, max_pages: Optional[int]
    ) -> Dict[str, Any]:
        """PyMuPDF (fitz) 라이브러리를 사용한 추출 (가장 빠름)."""
        import fitz
        
        pages_data = []
        all_text = []
        metadata = {}
        
        doc = fitz.open(pdf_path)
        
        # 메타데이터
        metadata = {
            "num_pages": len(doc),
            "title": doc.metadata.get("title", "제목 없음"),
            "author": doc.metadata.get("author", "작성자 없음"),
            "creation_date": doc.metadata.get("creationDate", "날짜 없음"),
        }
        
        # 페이지별 추출
        max_pages = max_pages or len(doc)
        for page_num in range(min(max_pages, len(doc))):
            page = doc[page_num]
            
            # 텍스트 추출
            text = page.get_text()
            text = self._normalize_text(text)
            all_text.append(text)
            
            # 테이블 추출 (PyMuPDF 방식)
            tables_data = []
            if extract_tables:
                try:
                    tables = page.find_tables()
                    for table_idx, table in enumerate(tables):
                        table_text = self._table_to_text(table.extract())
                        tables_data.append({
                            "bbox": table.bbox,
                            "content": table_text,
                            "rows": len(table.extract()),
                            "cols": len(table.extract()[0]) if table.extract() else 0,
                        })
                except Exception as e:
                    logger.debug(f"테이블 추출 실패 (페이지 {page_num + 1}): {e}")
            
            pages_data.append({
                "page_num": page_num + 1,
                "text": text,
                "tables": tables_data,
                "page_height": page.rect.height,
                "page_width": page.rect.width,
            })
            
            logger.debug(f"페이지 {page_num + 1} 추출: {len(text)} 문자, {len(tables_data)}개 테이블")
        
        doc.close()
        logger.info(f"✅ PDF 추출 완료: {len(pages_data)}개 페이지 (PyMuPDF)")
        
        return {
            "status": "success",
            "metadata": metadata,
            "pages": pages_data,
            "full_text": "\n\n--- 페이지 분리 ---\n\n".join(all_text),
        }
    
    def _extract_with_pdfplumber(
        self, pdf_path: Path, extract_tables: bool, max_pages: Optional[int]
    ) -> Dict[str, Any]:
        """pdfplumber 라이브러리를 사용한 추출."""
        import pdfplumber
        
        pages_data = []
        all_text = []
        metadata = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            # 메타데이터
            if pdf.metadata:
                metadata = {
                    "num_pages": len(pdf.pages),
                    "title": pdf.metadata.get("Title", "제목 없음"),
                    "author": pdf.metadata.get("Author", "작성자 없음"),
                    "creation_date": pdf.metadata.get("CreationDate", "날짜 없음"),
                }
            
            # 페이지별 추출
            max_pages = max_pages or len(pdf.pages)
            for page_num, page in enumerate(pdf.pages[:max_pages], start=1):
                # 텍스트 추출
                text = page.extract_text() or ""
                text = self._normalize_text(text)
                all_text.append(text)
                
                # 테이블 추출
                tables_data = []
                if extract_tables:
                    tables = page.extract_tables()
                    for table in (tables or []):
                        # 테이블 텍스트화
                        table_text = self._table_to_text(table)
                        tables_data.append({
                            "bbox": page.bbox,  # 페이지 경계
                            "content": table_text,
                            "rows": len(table),
                            "cols": len(table[0]) if table else 0,
                        })
                
                pages_data.append({
                    "page_num": page_num,
                    "text": text,
                    "tables": tables_data,
                    "page_height": page.height,
                    "page_width": page.width,
                })
                
                logger.debug(f"페이지 {page_num} 추출: {len(text)} 문자, {len(tables_data)}개 테이블")
        
        logger.info(f"✅ PDF 추출 완료: {len(pages_data)}개 페이지 (pdfplumber)")
        
        return {
            "status": "success",
            "metadata": metadata,
            "pages": pages_data,
            "full_text": "\n\n--- 페이지 분리 ---\n\n".join(all_text),
        }
    
    def _extract_with_pypdf(
        self, pdf_path: Path, extract_tables: bool, max_pages: Optional[int]
    ) -> Dict[str, Any]:
        """pypdf 라이브러리를 사용한 추출."""
        import pypdf
        
        pages_data = []
        all_text = []
        metadata = {}
        
        with open(pdf_path, "rb") as f:
            pdf_reader = pypdf.PdfReader(f)
            
            # 메타데이터
            if pdf_reader.metadata:
                metadata = {
                    "num_pages": len(pdf_reader.pages),
                    "title": pdf_reader.metadata.get("/Title", "제목 없음"),
                    "author": pdf_reader.metadata.get("/Author", "작성자 없음"),
                    "creation_date": pdf_reader.metadata.get("/CreationDate", "날짜 없음"),
                }
            
            # 페이지별 추출
            max_pages = max_pages or len(pdf_reader.pages)
            for page_num, page in enumerate(pdf_reader.pages[:max_pages], start=1):
                # 텍스트 추출 (table 감지는 제한적)
                text = page.extract_text()
                text = self._normalize_text(text)
                all_text.append(text)
                
                pages_data.append({
                    "page_num": page_num,
                    "text": text,
                    "tables": [],  # pypdf는 테이블 추출 미지원
                })
                
                logger.debug(f"페이지 {page_num} 추출: {len(text)} 문자")
        
        if not extract_tables:
            logger.info(f"✅ PDF 추출 완료: {len(pages_data)}개 페이지 (pypdf)")
        else:
            logger.warning("⚠️ pypdf는 테이블 추출 미지원. pdfplumber 설치 권장.")
        
        return {
            "status": "success",
            "metadata": metadata,
            "pages": pages_data,
            "full_text": "\n\n--- 페이지 분리 ---\n\n".join(all_text),
        }
    
    def _normalize_text(self, text: str) -> str:
        """
        텍스트 정규화 (불필요한 공백, 특수문자 처리).
        
        - 연속 공백 제거
        - 이상한 개행 제거
        - 제어 문자 제거
        """
        if not text:
            return ""
        
        # 제어 문자 제거
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
        
        # 연속 공백 정규화 (2개 이상 공백/탭 → 1개 공백)
        text = re.sub(r"[ \t]{2,}", " ", text)
        
        # 연속 개행 정규화 (3개 이상 → 2개)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # 개행 + 공백 정규화
        text = re.sub(r"\n[ \t]+", "\n", text)
        
        return text.strip()
    
    def _table_to_text(self, table: List[List[str]]) -> str:
        """
        테이블을 텍스트 형식으로 변환.
        
        | 행1열1 | 행1열2 |
        | 행2열1 | 행2열2 |
        """
        if not table:
            return ""
        
        # 각 열의 최대 너비 계산
        num_cols = max(len(row) for row in table) if table else 0
        col_widths = [0] * num_cols
        
        for row in table:
            for col_idx, cell in enumerate(row):
                col_widths[col_idx] = max(col_widths[col_idx], len(str(cell)))
        
        # 테이블 생성
        lines = []
        for row in table:
            cells = []
            for col_idx, cell in enumerate(row):
                cell_str = str(cell or "").ljust(col_widths[col_idx])
                cells.append(cell_str)
            lines.append("| " + " | ".join(cells) + " |")
        
        return "\n".join(lines)
    
    def batch_load_and_extract(self, pdf_paths: List[str]) -> List[Dict[str, Any]]:
        """
        여러 PDF 파일을 배치로 처리합니다.
        
        Args:
            pdf_paths (List[str]): PDF 파일 경로 리스트
        
        Returns:
            List[Dict[str, Any]]: 추출 결과 리스트
        """
        results = []
        for pdf_path in pdf_paths:
            try:
                result = self.load_and_extract(pdf_path)
                results.append(result)
                logger.debug(f"✅ {pdf_path} 처리 완료")
            except Exception as e:
                logger.error(f"PDF 처리 오류: {pdf_path}, {e}")
                results.append({"status": "error", "error": str(e), "path": pdf_path})
        
        logger.info(f"✅ {len(results)}개 PDF 배치 처리 완료")
        return results
