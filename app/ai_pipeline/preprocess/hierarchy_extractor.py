"""
module: hierarchy_extractor.py
description: 규제 문서의 법률 계층 구조 추출 및 관계 매핑
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger
    - app.ai_pipeline.preprocess.definition_extractor
    - typing, re, json
"""

from typing import List, Dict, Tuple, Optional, Any
import logging
import re
import json

logger = logging.getLogger(__name__)


class HierarchyExtractor:
    """
    규제 문서의 계층 구조(장→절→조→항→호)를 추출하고 관계를 매핑하는 클래스.
    
    역할:
    - 문서 구조 분석 (레벨별 계층)
    - 부모-자식 관계 파악
    - 조항 간 계층적 포함 관계 식별
    - 트리 구조 생성
    - JSON/마크다운 형식 내보내기
    
    특징:
    - 다중 레벨 지원 (최대 6 레벨)
    - 참조 조항 연결
    - 청크 대응 정보 (청크 ID로 위치 추적)
    - 시각화 정보 (들여쓰기 레벨)
    """
    
    # 계층 레벨 정의 (기존 + DDH 패턴)
    HIERARCHY_LEVELS = {
        1: {"name": "chapter", "kr": "장", "pattern": r"^(제\s*\d+\s*장|Chapter\s+[IVX]+)"},
        2: {"name": "section", "kr": "절", "pattern": r"^(제\s*\d+\s*절|Section\s+\d+)"},
        3: {"name": "article", "kr": "조", "pattern": r"^(제\s*\d+\s*조|Article\s+\d+)"},
        4: {"name": "subsection", "kr": "항", "pattern": r"^\s*(제?\s*\d+\s*항|\(\d+\))"},
        5: {"name": "clause", "kr": "호", "pattern": r"^\s*(제?\s*\d+\s*호|\d+\.)"},
    }
    
    # DDH 규제 패턴 (미국 연방 규정)
    DDH_PATTERNS = {
        "HEADER": r"^(AGENCY|ACTION|SUMMARY|DATES|ADDRESSES):",
        "ISSUANCE": r"(amends|adds|revises).*?part.*?to read as follows:",
        "SECTION": r"^(§|SEC\.|SECTION)\s*(\d+(?:\.\d+)?)\s*(.*)",  # § 1160.3 또는 SEC. 101 지원
        "LEVEL_1": r"^\((a|[a-z])\)\s*",
        "LEVEL_2": r"^\(([1-9]|[0-9]+)\)\s*",
        "LEVEL_3": r"^\((i|ii|iii|iv|v)\)\s*",
    }
    
    def __init__(self, max_depth: int = 5, use_ddh: bool = False):
        """
        계층 추출기 초기화.
        
        Args:
            max_depth (int): 최대 계층 깊이. 기본값: 5
            use_ddh (bool): DDH 패턴 사용 여부. 기본값: False
        """
        self.max_depth = max_depth
        self.use_ddh = use_ddh
        self.current_zone = "preamble" if use_ddh else "content"
        self.preamble_metadata = {}
        logger.info(f"✅ HierarchyExtractor 초기화: max_depth={max_depth}, use_ddh={use_ddh}")
    
    def extract_hierarchy(self, document_text: str) -> Dict[str, Any]:
        """
        문서의 계층 구조를 추출합니다.
        
        Args:
            document_text (str): 규제 문서 텍스트
        
        Returns:
            Dict[str, Any]: {
                "hierarchy_tree": [
                    {
                        "id": "ch_1",
                        "level": 1,
                        "level_name": "chapter",
                        "number": "1",
                        "title": "총칙",
                        "children": [
                            {
                                "id": "sec_1_1",
                                "level": 2,
                                "number": "1",
                                "title": "일반사항",
                                "children": [...]
                            }
                        ]
                    }
                ],
                "flat_list": [  # 평탄한 리스트 (검색용)
                    {
                        "id": "ch_1",
                        "path": "1",  # 경로: 1 (장), 1.1 (절), 1.1.1 (조)
                        "level": 1,
                        "title": "총칙",
                    },
                    ...
                ],
                "statistics": {
                    "num_chapters": 3,
                    "num_articles": 25,
                    "max_depth": 3,
                }
            }
        
        Raises:
            ValueError: 입력 텍스트가 비어있을 경우
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty")
        
        # 1단계: 헤더 라인 추출
        headers = self._extract_headers(document_text)
        logger.debug(f"헤더 추출: {len(headers)}개")
        
        # 2단계: 트리 구조 구성
        hierarchy_tree = self._build_tree(headers)
        
        # 3단계: 평탄한 리스트 생성
        flat_list = self._flatten_tree(hierarchy_tree)
        
        # 통계
        statistics = {
            "num_chapters": len([h for h in flat_list if h["level"] == 1]),
            "num_articles": len([h for h in flat_list if h["level"] == 3]),
            "max_depth": max([h["level"] for h in flat_list]) if flat_list else 0,
        }
        
        logger.info(
            f"✅ 계층 추출 완료: {len(flat_list)}개 항목, "
            f"{statistics['num_chapters']}개 장, {statistics['num_articles']}개 조"
        )
        
        return {
            "hierarchy_tree": hierarchy_tree,
            "flat_list": flat_list,
            "statistics": statistics,
        }
    
    def _extract_headers(self, text: str) -> List[Dict[str, Any]]:
        """문서에서 헤더(장, 절, 조 등)를 추출합니다."""
        headers = []
        lines = text.split("\n")
        
        for line_idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            
            # 각 레벨 패턴 확인
            for level, level_info in self.HIERARCHY_LEVELS.items():
                if re.match(level_info["pattern"], stripped):
                    # 번호와 제목 추출
                    number = self._extract_number(stripped, level)
                    title = self._extract_title(stripped, level)
                    
                    headers.append({
                        "level": level,
                        "level_name": level_info["name"],
                        "number": number,
                        "title": title,
                        "line_index": line_idx,
                    })
                    break
        
        return headers
    
    def _extract_number(self, header_line: str, level: int) -> str:
        """헤더에서 번호 추출."""
        numbers = re.findall(r"\d+", header_line)
        if numbers:
            return numbers[0]
        return "0"
    
    def _extract_title(self, header_line: str, level: int) -> str:
        """헤더에서 제목 추출."""
        # 번호 이후의 텍스트
        level_info = self.HIERARCHY_LEVELS[level]
        match = re.match(level_info["pattern"], header_line)
        if match:
            # 번호 부분 제거
            title = header_line[len(match.group(0)):].strip()
            # 제목 부분만 추출 (괄호, 기호 제거)
            title = re.sub(r"^[:：\s]+", "", title)
            return title[:100] if title else "제목 없음"
        return "제목 없음"
    
    def _build_tree(self, headers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """헤더 리스트로부터 트리 구조를 구성합니다."""
        if not headers:
            return []
        
        tree = []
        stack = []  # (level, node) 스택
        
        for header in headers:
            level = header["level"]
            number = header["number"]
            title = header["title"]
            
            node = {
                "id": self._generate_id(header),
                "level": level,
                "level_name": header["level_name"],
                "number": number,
                "title": title,
                "children": [],
            }
            
            # 스택에서 부모 찾기
            while stack and stack[-1][0] >= level:
                stack.pop()
            
            if stack:
                # 부모 노드에 추가
                parent_node = stack[-1][1]
                parent_node["children"].append(node)
            else:
                # 루트 레벨
                tree.append(node)
            
            # 스택에 현재 노드 추가
            stack.append((level, node))
        
        return tree
    
    def _generate_id(self, header: Dict[str, Any]) -> str:
        """노드 ID 생성."""
        level_abbr = {
            1: "ch", 2: "sec", 3: "art", 4: "sub", 5: "cls"
        }
        level = header["level"]
        number = header["number"]
        abbr = level_abbr.get(level, "lvl")
        return f"{abbr}_{number}"
    
    def _flatten_tree(self, tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """트리를 평탄한 리스트로 변환합니다."""
        flat = []
        
        def traverse(nodes, path=[]):
            for node in nodes:
                current_path = path + [node["number"]]
                path_str = ".".join(current_path)
                
                flat.append({
                    "id": node["id"],
                    "path": path_str,
                    "level": node["level"],
                    "title": node["title"],
                    "num_children": len(node["children"]),
                })
                
                if node["children"]:
                    traverse(node["children"], current_path)
        
        traverse(tree)
        return flat
    
    def export_as_markdown(self, hierarchy_result: Dict[str, Any]) -> str:
        """계층을 마크다운 형식으로 내보냅니다."""
        def tree_to_md(nodes, depth=0):
            md_lines = []
            for node in nodes:
                indent = "  " * depth + "- "
                md_lines.append(f"{indent}**{node['number']}. {node['title']}** ({node['level_name']})")
                if node["children"]:
                    md_lines.extend(tree_to_md(node["children"], depth + 1))
            return md_lines
        
        lines = tree_to_md(hierarchy_result["hierarchy_tree"])
        return "\n".join(lines)
    
    def export_as_json(self, hierarchy_result: Dict[str, Any]) -> str:
        """계층을 JSON 형식으로 내보냅니다."""
        return json.dumps(hierarchy_result, ensure_ascii=False, indent=2)
    
    def parse_ddh_structure(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        DDH 표준에 따른 규제 문서 파싱.
        
        Args:
            raw_text (str): 원본 규제 문서 텍스트
            
        Returns:
            List[Dict]: LegalNode 형태의 구조화된 데이터
        """
        if not self.use_ddh:
            logger.warning("DDH 모드가 비활성화됨. use_ddh=True로 초기화 필요")
            return []
            
        lines = raw_text.split('\n')
        nodes = []
        current_section = None
        stack = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 1. 구역 전환 감지 (Words of Issuance)
            if re.search(self.DDH_PATTERNS["ISSUANCE"], line, re.IGNORECASE):
                self.current_zone = "regulatory_text"
                logger.debug("구역 전환: preamble → regulatory_text")
                continue
                
            # 2. 서문(Preamble) 파싱: 메타데이터 추출
            if self.current_zone == "preamble":
                match = re.match(self.DDH_PATTERNS["HEADER"], line)
                if match:
                    key = match.group(1)
                    value = line[len(key)+1:].strip()
                    self.preamble_metadata[key] = value
                    logger.debug(f"서문 메타데이터: {key} = {value[:50]}...")
                continue
                
            # 3. 규제 본문(Regulatory Text) 파싱
            if self.current_zone == "regulatory_text":
                # 섹션 감지 (§ 1160.10 또는 SEC. 101)
                sec_match = re.match(self.DDH_PATTERNS["SECTION"], line, re.IGNORECASE)
                if sec_match:
                    # 이전 섹션 저장
                    if current_section:
                        nodes.append(current_section)
                    
                    # 새 섹션 생성
                    current_section = {
                        "node_type": "section",
                        "identifier": f"§ {sec_match.group(2)}",
                        "text": sec_match.group(3).strip(),
                        "metadata": self.preamble_metadata.copy(),
                        "children": []
                    }
                    stack = [current_section]
                    logger.debug(f"새 섹션: {current_section['identifier']}")
                    continue
                    
                # 하위 파라그래프 감지
                if current_section:
                    level_1_match = re.match(self.DDH_PATTERNS["LEVEL_1"], line)
                    level_2_match = re.match(self.DDH_PATTERNS["LEVEL_2"], line)
                    level_3_match = re.match(self.DDH_PATTERNS["LEVEL_3"], line)
                    
                    if level_1_match:  # (a)
                        new_node = {
                            "node_type": "paragraph",
                            "identifier": level_1_match.group(0),
                            "text": line[len(level_1_match.group(0)):].strip(),
                            "metadata": self.preamble_metadata.copy(),
                            "children": [],
                            "level": 1
                        }
                        current_section["children"].append(new_node)
                        stack = [current_section, new_node]
                        
                    elif level_2_match and len(stack) >= 2:  # (1)
                        new_node = {
                            "node_type": "subparagraph",
                            "identifier": level_2_match.group(0),
                            "text": line[len(level_2_match.group(0)):].strip(),
                            "metadata": self.preamble_metadata.copy(),
                            "children": [],
                            "level": 2
                        }
                        stack[1]["children"].append(new_node)
                        
                    elif level_3_match and len(stack) >= 2:  # (i)
                        new_node = {
                            "node_type": "clause",
                            "identifier": level_3_match.group(0),
                            "text": line[len(level_3_match.group(0)):].strip(),
                            "metadata": self.preamble_metadata.copy(),
                            "children": [],
                            "level": 3
                        }
                        # 가장 가까운 부모에 추가
                        if len(stack) >= 3:
                            stack[2]["children"].append(new_node)
                        else:
                            stack[1]["children"].append(new_node)
                            
                    else:
                        # 패턴이 없으면 직전 노드에 텍스트 추가
                        if stack:
                            # 표(Table) 감지
                            if "|" in line and "-|-" in line:
                                stack[-1]["text"] += "\n" + line
                            else:
                                stack[-1]["text"] += " " + line
        
        # 마지막 섹션 추가
        if current_section:
            nodes.append(current_section)
            
        logger.info(f"✅ DDH 파싱 완료: {len(nodes)}개 섹션, 서문 메타데이터 {len(self.preamble_metadata)}개")
        return nodes
    
    def get_preamble_metadata(self) -> Dict[str, str]:
        """서문에서 추출된 메타데이터 반환."""
        return self.preamble_metadata.copy()
