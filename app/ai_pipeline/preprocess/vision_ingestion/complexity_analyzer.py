"""
module: complexity_analyzer.py
description: 페이지 복잡도 분석 (표 감지)
author: AI Agent
created: 2025-01-14
dependencies: pdfplumber
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """페이지 복잡도 분석기 (표 감지 기반)."""
    
    def __init__(self):
        pass
        
    def analyze_page(self, pdf_path: str, page_num: int) -> Dict[str, Any]:
        """
        페이지 복잡도 점수 계산.
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (1-based)
            
        Returns:
            Dict: {
                "has_table": bool,
                "complexity_score": float,  # 0-1
                "table_count": int,
                "line_intersections": int
            }
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber가 설치되지 않았습니다: pip install pdfplumber")
        
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num - 1]
            
            # 표 감지
            tables = page.find_tables()
            table_count = len(tables)
            has_table = table_count > 0
            
            # 라인 교차점 계산
            lines = page.lines
            h_lines = [l for l in lines if l.get("orientation") == "h"]
            v_lines = [l for l in lines if l.get("orientation") == "v"]
            
            # 간단한 교차점 추정 (정확한 계산은 비용 높음)
            intersections = len(h_lines) * len(v_lines) if has_table else 0
            
            # 복잡도 점수 (0-1)
            # 표가 있으면 0.5 이상, 교차점 많으면 1.0에 가까움
            if has_table:
                complexity_score = min(0.5 + (intersections / 1000), 1.0)
            else:
                complexity_score = 0.1
            
            result = {
                "has_table": has_table,
                "complexity_score": complexity_score,
                "table_count": table_count,
                "line_intersections": intersections
            }
            
            logger.debug(f"페이지 {page_num} 복잡도: {complexity_score:.2f} (표: {table_count}개)")
            
            return result
