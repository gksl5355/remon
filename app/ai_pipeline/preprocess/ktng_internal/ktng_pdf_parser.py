"""
module: ktng_pdf_parser.py
description: KTNG 내부 데이터 PDF 파싱 (규제+제품 추출)
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - app.ai_pipeline.preprocess.pdf_processor
"""

from typing import List, Dict, Any
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class KTNGPDFParser:
    """KTNG 내부 데이터 PDF 파싱 클래스."""
    
    def __init__(self):
        """초기화."""
        from app.ai_pipeline.preprocess.pdf_processor import PDFProcessor
        self.pdf_processor = PDFProcessor()
        
    def parse_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        KTNG PDF에서 규제-제품 쌍 추출.
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            List[Dict]: [
                {
                    "regulation_text": "니코틴 함량 제한...",
                    "products": ["제품A", "제품B"],
                    "product_specs": {"nicotine": "18mg", "category": "e-cigarette"},
                    "page_number": 5,
                    "section": "대응전략_1"
                }
            ]
        """
        logger.info(f"KTNG PDF 파싱 시작: {pdf_path}")
        
        # PDF 텍스트 추출
        pdf_result = self.pdf_processor.load_and_extract(pdf_path)
        if pdf_result["status"] != "success":
            raise RuntimeError(f"PDF 추출 실패: {pdf_result.get('error')}")
        
        raw_text = pdf_result.get("full_text", "")
        
        # 규제-제품 쌍 추출
        parsed_data = self._extract_regulation_product_pairs(raw_text)
        
        logger.info(f"KTNG PDF 파싱 완료: {len(parsed_data)}개 규제-제품 쌍")
        return parsed_data
    
    def _extract_regulation_product_pairs(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 규제-제품 쌍 추출."""
        pairs = []
        
        # 페이지별로 분할
        pages = self._split_by_pages(text)
        
        for page_num, page_text in enumerate(pages, 1):
            # 섹션별로 분할
            sections = self._extract_sections(page_text)
            
            for section_name, section_text in sections.items():
                # 규제 내용 추출
                regulations = self._extract_regulations(section_text)
                
                # 제품 정보 추출
                products = self._extract_products(section_text)
                
                # 제품 스펙 추출
                product_specs = self._extract_product_specs(section_text)
                
                if regulations and products:
                    pairs.append({
                        "regulation_text": " ".join(regulations),
                        "products": products,
                        "product_specs": product_specs,
                        "page_number": page_num,
                        "section": section_name,
                        "raw_section_text": section_text[:500]  # 디버깅용
                    })
        
        return pairs
    
    def _split_by_pages(self, text: str) -> List[str]:
        """텍스트를 페이지별로 분할."""
        # 간단한 페이지 분할 (실제로는 PDF 메타데이터 활용)
        pages = text.split('\n\n\n')  # 큰 공백으로 페이지 구분
        return [page.strip() for page in pages if page.strip()]
    
    def _extract_sections(self, page_text: str) -> Dict[str, str]:
        """페이지에서 섹션 추출."""
        sections = {}
        
        # 섹션 패턴 (예: "1. 대응전략", "2. 제품 분석" 등)
        section_pattern = r'(\d+\.\s*[^.\n]+)'
        matches = re.finditer(section_pattern, page_text)
        
        section_starts = [(m.start(), m.group(1)) for m in matches]
        
        for i, (start, title) in enumerate(section_starts):
            end = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(page_text)
            section_content = page_text[start:end].strip()
            sections[title.strip()] = section_content
        
        # 섹션이 없으면 전체를 하나의 섹션으로
        if not sections:
            sections["전체"] = page_text
        
        return sections
    
    def _extract_regulations(self, text: str) -> List[str]:
        """텍스트에서 규제 내용 추출."""
        regulations = []
        
        # 규제 관련 키워드 패턴
        regulation_patterns = [
            r'니코틴\s*함량[^.]*[.]',
            r'라벨\s*크기[^.]*[.]',
            r'경고\s*문구[^.]*[.]',
            r'배터리\s*용량[^.]*[.]',
            r'인증\s*요구사항[^.]*[.]',
            r'규제\s*[^.]*[.]',
            r'제한\s*[^.]*[.]',
            r'요구사항\s*[^.]*[.]'
        ]
        
        for pattern in regulation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            regulations.extend(matches)
        
        return list(set(regulations))  # 중복 제거
    
    def _extract_products(self, text: str) -> List[str]:
        """텍스트에서 제품명 추출."""
        products = []
        
        # 제품명 패턴
        product_patterns = [
            r'제품\s*[A-Z가-힣0-9]+',
            r'[A-Z가-힣]+\s*전자담배',
            r'[A-Z가-힣]+\s*궐련',
            r'모델\s*[A-Z가-힣0-9]+',
        ]
        
        for pattern in product_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            products.extend(matches)
        
        return list(set(products))  # 중복 제거
    
    def _extract_product_specs(self, text: str) -> Dict[str, Any]:
        """텍스트에서 제품 스펙 추출."""
        specs = {}
        
        # 니코틴 함량
        nicotine_match = re.search(r'니코틴\s*[:：]?\s*(\d+(?:\.\d+)?)\s*mg', text, re.IGNORECASE)
        if nicotine_match:
            specs["nicotine"] = float(nicotine_match.group(1))
        
        # 배터리 용량
        battery_match = re.search(r'배터리\s*[:：]?\s*(\d+)\s*mAh', text, re.IGNORECASE)
        if battery_match:
            specs["battery_capacity"] = int(battery_match.group(1))
        
        # 라벨 크기
        label_match = re.search(r'라벨\s*[:：]?\s*(\d+(?:\.\d+)?)\s*cm', text, re.IGNORECASE)
        if label_match:
            specs["label_size"] = float(label_match.group(1))
        
        # 제품 카테고리
        if "전자담배" in text:
            specs["category"] = "e-cigarette"
        elif "궐련" in text:
            specs["category"] = "cigarette"
        elif "담배" in text:
            specs["category"] = "tobacco"
        
        return specs