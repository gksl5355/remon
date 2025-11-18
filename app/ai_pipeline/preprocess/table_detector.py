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
    문서에서 테이블 영역을 감지하고 구조를 분석하는 클래스.
    
    역할:
    - 테이블 텍스트 패턴 인식 (|, -, 등 구분자)
    - 테이블 경계 감지
    - 행(row), 열(column) 구조 파악
    - 테이블 메타데이터 추출 (크기, 데이터 타입 등)
    - 테이블과 일반 텍스트 분리
    
    특징:
    - 정규표현식 기반 (외부 라이브러리 불필요)
    - 다양한 테이블 형식 지원 (Markdown, HTML, 텍스트)
    - 테이블 위치 정보 제공
    """
    
    # 테이블 감지 패턴들
    TABLE_PATTERNS = {
        "markdown": r"\|.+\|",  # | 로 구분된 행
        "plain_pipe": r"^\|[\s\S]+?\|$",  # 시작-끝이 | 인 행들
        "grid": r"^\+[-=]+\+",  # +--+ 형태 (ASCII 테이블)
        "tab_separated": r"^\t.+\t",  # 탭으로 구분
        "spaced": r"(?:^|\n)\s{2,}\S+(?:\s{2,}\S+)+(?:\n|$)",  # 2칸 이상 공백으로 구분
    }
    
    def __init__(self, min_rows: int = 2, min_cols: int = 2):
        """
        테이블 감지기 초기화.
        
        Args:
            min_rows (int): 테이블 최소 행 수. 기본값: 2
            min_cols (int): 테이블 최소 열 수. 기본값: 2
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        logger.info(f"✅ TableDetector 초기화: min_rows={min_rows}, min_cols={min_cols}")
    
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
    
    def detect_tables_in_text(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 테이블을 감지합니다.
        
        Args:
            text (str): 분석 대상 텍스트
        
        Returns:
            Dict[str, Any]: {
                "num_tables": 감지된 테이블 수,
                "tables": [
                    {
                        "table_id": "table_0",
                        "type": "markdown" | "grid" | "tab_separated" | "unknown",
                        "start_line": 시작 라인 번호,
                        "end_line": 종료 라인 번호,
                        "num_rows": 행 수,
                        "num_cols": 열 수,
                        "headers": ["헤더1", "헤더2", ...],
                        "preview": "테이블 프리뷰 (텍스트)",
                        "bbox": {"line_start": X, "line_end": Y}  # 위치 정보
                    },
                    ...
                ],
                "non_table_text": "테이블 제거된 텍스트"
            }
        
        Raises:
            ValueError: 입력 텍스트가 비어있을 경우
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        lines = text.split("\n")
        tables = []
        table_regions = []  # 테이블 영역 (라인 범위)
        
        # 각 테이블 패턴으로 감지
        for table_type, pattern in self.TABLE_PATTERNS.items():
            tables_found = self._detect_by_pattern(lines, pattern, table_type)
            tables.extend(tables_found)
            table_regions.extend([(t["start_line"], t["end_line"]) for t in tables_found])
        
        # 테이블 정보 구성
        result_tables = []
        for idx, table in enumerate(tables):
            result_tables.append({
                "table_id": f"table_{idx}",
                "type": table["type"],
                "start_line": table["start_line"],
                "end_line": table["end_line"],
                "num_rows": table["num_rows"],
                "num_cols": table["num_cols"],
                "headers": table.get("headers", []),
                "preview": table.get("preview", "")[:200],
                "json_structure": self._extract_table_json(table),
                "has_reference": self._check_table_reference(lines, table["start_line"]),
                "bbox": {
                    "line_start": table["start_line"],
                    "line_end": table["end_line"],
                },
            })
        
        # 테이블 제거된 텍스트
        non_table_lines = self._remove_table_lines(lines, table_regions)
        non_table_text = "\n".join(non_table_lines)
        
        logger.info(f"✅ 테이블 감지 완료: {len(result_tables)}개 테이블 발견")
        
        return {
            "num_tables": len(result_tables),
            "tables": result_tables,
            "non_table_text": non_table_text,
        }
    
    def extract_table_content(self, text: str, table_id: str) -> Dict[str, Any]:
        """
        특정 테이블의 내용을 구조적으로 추출합니다.
        
        Args:
            text (str): 원본 텍스트
            table_id (str): 테이블 ID (예: "table_0")
        
        Returns:
            Dict[str, Any]: {
                "table_id": "table_0",
                "headers": ["헤더1", "헤더2"],
                "rows": [
                    {"col1": "값1", "col2": "값2"},
                    ...
                ],
                "num_rows": 행 수,
                "num_cols": 열 수,
            }
        """
        # 간단한 구현 (실제로는 더 복잡한 파싱 필요)
        result = {
            "table_id": table_id,
            "headers": [],
            "rows": [],
            "num_rows": 0,
            "num_cols": 0,
        }
        
        logger.debug(f"테이블 내용 추출: {table_id}")
        return result
    
    def _extract_table_json(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """테이블을 JSON 구조로 변환."""
        lines = table.get("preview", "").split("\n")
        if not lines or len(lines) < 2:
            return {"headers": [], "rows": [], "row_count": 0, "col_count": 0}
        
        headers = [cell.strip() for cell in lines[0].split("|") if cell.strip()]
        rows = []
        for line in lines[2:]:  # Skip header and separator
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                rows.append(cells)
        
        return {
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "col_count": len(headers)
        }
    
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
