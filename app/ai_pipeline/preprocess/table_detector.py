"""
module: table_detector.py
description: 문서에서 테이블 영역 감지 및 구조 분석
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger
    - app.ai_pipeline.preprocess.config
    - typing, re, regex-based detection
"""

from typing import List, Dict, Tuple, Optional, Any
import logging
import re

logger = logging.getLogger(__name__)


class TableDetector:
    """
    청킹 전략에 통합된 테이블 감지 및 Markdown 변환기.
    
    역할:
    - 테이블 패턴 감지 (|, -, 공백 구분)
    - Markdown 형식으로 정규화
    - 청킹 시 테이블 무결성 보장
    """
    
    # 테이블 감지 패턴 (간소화)
    TABLE_PATTERNS = [
        r"\|.+\|",  # Markdown 테이블
        r"^\+[-=]+\+",  # ASCII 테이블
        r"\s{3,}\S+(?:\s{3,}\S+){2,}",  # 공백 구분 (3칸 이상, 3열 이상)
    ]
    
    def __init__(self):
        """테이블 감지기 초기화 (청킹 통합용)."""
        logger.info("✅ TableDetector 초기화 (청킹 통합)")
    
    def _check_table_reference(self, lines: List[str], table_idx: int, direction: str = "before") -> bool:
        """표 참조 문구 확인."""
        patterns = [
            r'[Tt]able\s+\d+',
            r'following\s+table',
            r'above\s+table',
            r'preceding\s+table',
            r'as\s+shown\s+in\s+[Tt]able',
            r'see\s+[Tt]able'
        ]
        
        if direction == "before" and table_idx > 0:
            prev_text = lines[table_idx - 1] if table_idx > 0 else ""
            return any(re.search(p, prev_text) for p in patterns)
        elif direction == "after" and table_idx < len(lines) - 1:
            next_text = lines[table_idx + 1] if table_idx < len(lines) - 1 else ""
            return any(re.search(p, next_text) for p in patterns)
        
        return False
    
    def detect_and_convert_tables(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 테이블을 감지하고 Markdown으로 변환.
        
        Returns:
            Dict[str, Any]: {
                "converted_text": "테이블이 Markdown으로 변환된 텍스트",
                "table_regions": [(start, end), ...],  # 테이블 위치
                "num_tables": 감지된 테이블 수
            }
        """
        if not text or not text.strip():
            return {"converted_text": text, "table_regions": [], "num_tables": 0}
        
        lines = text.split("\n")
        converted_lines = lines.copy()
        table_regions = []
        
        # 테이블 패턴 감지 및 변환
        for pattern in self.TABLE_PATTERNS:
            i = 0
            while i < len(converted_lines):
                if re.search(pattern, converted_lines[i]):
                    # 연속된 테이블 행 찾기
                    start_line = i
                    table_lines = []
                    while i < len(converted_lines) and re.search(pattern, converted_lines[i]):
                        table_lines.append(converted_lines[i])
                        i += 1
                    
                    # Markdown 테이블로 변환
                    if len(table_lines) >= 2:  # 최소 2행
                        markdown_table = self._convert_to_markdown(table_lines)
                        # 원본 라인들을 Markdown으로 교체
                        converted_lines[start_line:start_line + len(table_lines)] = markdown_table.split("\n")
                        table_regions.append((start_line, start_line + len(table_lines) - 1))
                else:
                    i += 1
        
        converted_text = "\n".join(converted_lines)
        
        logger.debug(f"✅ 테이블 변환 완료: {len(table_regions)}개 테이블")
        
        return {
            "converted_text": converted_text,
            "table_regions": table_regions,
            "num_tables": len(table_regions)
        }
    
    def _convert_to_markdown(self, table_lines: List[str]) -> str:
        """
        테이블 라인들을 Markdown 형식으로 변환.
        
        Args:
            table_lines: 테이블 라인 리스트
        
        Returns:
            str: Markdown 테이블 문자열
        """
        if not table_lines:
            return ""
        
        # 이미 Markdown 형식인지 확인
        if all("|" in line for line in table_lines[:2]):
            return "\n".join(table_lines)
        
        # 공백 구분 테이블을 Markdown으로 변환
        markdown_lines = []
        for i, line in enumerate(table_lines):
            # 공백으로 구분된 셀들을 | 구분자로 변환
            cells = re.split(r'\s{2,}', line.strip())
            if len(cells) >= 2:
                markdown_line = "| " + " | ".join(cells) + " |"
                markdown_lines.append(markdown_line)
                
                # 첫 번째 행 후에 구분자 추가
                if i == 0:
                    separator = "| " + " | ".join(["---"] * len(cells)) + " |"
                    markdown_lines.append(separator)
        
        return "\n".join(markdown_lines)
    
    def is_table_region(self, line_num: int, table_regions: List[Tuple[int, int]]) -> bool:
        """
        특정 라인이 테이블 영역에 속하는지 확인.
        
        Args:
            line_num: 라인 번호
            table_regions: 테이블 영역 리스트 [(start, end), ...]
        
        Returns:
            bool: 테이블 영역 여부
        """
        return any(start <= line_num <= end for start, end in table_regions)
    
    def _detect_by_pattern(self, lines: List[str], pattern: str, pattern_type: str) -> List[Dict[str, Any]]:
        """
        패턴으로 테이블 감지.
        """
        tables = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 패턴 일치
            if re.search(pattern, line, re.MULTILINE):
                # 연속된 테이블 행 찾기
                table_start = i
                while i < len(lines) and re.search(pattern, lines[i], re.MULTILINE):
                    i += 1
                table_end = i - 1
                
                # 테이블 크기 확인
                num_rows = table_end - table_start + 1
                num_cols = self._count_columns(lines[table_start:i], pattern_type)
                
                if num_rows >= self.min_rows and num_cols >= self.min_cols:
                    table_text = "\n".join(lines[table_start:i])
                    headers = self._extract_headers(lines[table_start:i], pattern_type)
                    
                    tables.append({
                        "type": pattern_type,
                        "start_line": table_start,
                        "end_line": table_end,
                        "num_rows": num_rows,
                        "num_cols": num_cols,
                        "headers": headers,
                        "preview": table_text[:100],
                    })
                    
                    logger.debug(
                        f"테이블 감지 ({pattern_type}): "
                        f"라인 {table_start}-{table_end}, {num_rows}x{num_cols}"
                    )
            else:
                i += 1
        
        return tables
    
    def _count_columns(self, lines: List[str], pattern_type: str) -> int:
        """테이블의 열 수를 세기."""
        if not lines:
            return 0
        
        first_line = lines[0]
        
        if pattern_type == "markdown":
            # Markdown 테이블: | col1 | col2 | → 2 columns
            return first_line.count("|") - 1
        elif pattern_type == "plain_pipe":
            return first_line.count("|") - 1
        elif pattern_type == "tab_separated":
            # 탭 구분: col1\tcol2 → 2 columns
            return first_line.count("\t") + 1
        elif pattern_type == "spaced":
            # 공백 구분: col1  col2  col3 → 3 columns
            return len(re.split(r"\s{2,}", first_line.strip()))
        else:
            return 1
    
    def _extract_headers(self, lines: List[str], pattern_type: str) -> List[str]:
        """테이블 헤더 추출."""
        if not lines:
            return []
        
        first_line = lines[0]
        
        if pattern_type == "markdown" or pattern_type == "plain_pipe":
            # | header1 | header2 | → ["header1", "header2"]
            cells = first_line.split("|")
            headers = [cell.strip() for cell in cells if cell.strip()]
            return headers
        elif pattern_type == "tab_separated":
            # header1\theader2 → ["header1", "header2"]
            return first_line.split("\t")
        elif pattern_type == "spaced":
            # header1  header2 → ["header1", "header2"]
            return re.split(r"\s{2,}", first_line.strip())
        else:
            return []
    
    def _remove_table_lines(self, lines: List[str], table_regions: List[Tuple[int, int]]) -> List[str]:
        """테이블 영역을 텍스트에서 제거."""
        if not table_regions:
            return lines
        
        # 테이블 라인 인덱스 수집
        table_line_indices = set()
        for start, end in table_regions:
            for idx in range(start, end + 1):
                table_line_indices.add(idx)
        
        # 테이블이 아닌 라인만 반환
        non_table_lines = [
            line for idx, line in enumerate(lines)
            if idx not in table_line_indices
        ]
        
        return non_table_lines
    
    def get_statistics(self, detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        테이블 감지 결과의 통계를 반환합니다.
        
        Args:
            detection_result (Dict[str, Any]): detect_tables_in_text 결과
        
        Returns:
            Dict[str, Any]: 통계 정보
        """
        tables = detection_result.get("tables", [])
        
        if not tables:
            return {
                "num_tables": 0,
                "total_rows": 0,
                "total_cols": 0,
                "avg_rows_per_table": 0,
                "avg_cols_per_table": 0,
            }
        
        total_rows = sum(t["num_rows"] for t in tables)
        total_cols = sum(t["num_cols"] for t in tables)
        
        return {
            "num_tables": len(tables),
            "total_rows": total_rows,
            "total_cols": total_cols,
            "avg_rows_per_table": round(total_rows / len(tables), 2),
            "avg_cols_per_table": round(total_cols / len(tables), 2),
            "table_types": list(set(t["type"] for t in tables)),
        }
    
    def bind_table_context(self, text: str, tables: List[Dict[str, Any]], context_chars: int = 300) -> List[Dict[str, Any]]:
        """표 주변 설명 문단을 표와 바인딩."""
        lines = text.split("\n")
        enriched_tables = []
        
        for table in tables:
            start_line = table.get("start_line", 0)
            end_line = table.get("end_line", 0)
            
            # 앞 맥락
            before_context = ""
            for i in range(max(0, start_line - 3), start_line):
                if i < len(lines):
                    before_context += lines[i] + "\n"
            before_context = before_context[-context_chars:]
            
            # 뒤 맥락
            after_context = ""
            for i in range(end_line + 1, min(len(lines), end_line + 4)):
                if i < len(lines):
                    after_context += lines[i] + "\n"
            after_context = after_context[:context_chars]
            
            enriched_tables.append({
                **table,
                "before_context": before_context.strip(),
                "after_context": after_context.strip(),
                "full_content": f"{before_context}\n{table.get('preview', '')}\n{after_context}".strip()
            })
        
        return enriched_tables
    
    def batch_detect_tables(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        여러 문서에서 테이블을 배치로 감지합니다.
        
        Args:
            documents (List[Dict[str, str]]): [{"text": "문서 텍스트"}, ...]
        
        Returns:
            List[Dict[str, Any]]: 감지 결과 리스트
        """
        results = []
        for doc in documents:
            try:
                detection = self.detect_tables_in_text(doc.get("text", ""))
                results.append(detection)
                logger.debug(f"✅ 문서 테이블 감지 완료: {detection['num_tables']}개")
            except Exception as e:
                logger.error(f"테이블 감지 오류: {e}")
                results.append({"num_tables": 0, "tables": [], "error": str(e)})
        
        logger.info(f"✅ {len(results)}개 문서 테이블 감지 완료")
        return results
