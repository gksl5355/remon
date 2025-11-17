"""
module: ktng_chunking_strategy.py
description: 규제-제품 결합 청킹 전략
author: AI Agent
created: 2025-01-14
updated: 2025-01-14
dependencies:
    - app.ai_pipeline.preprocess.semantic_chunker
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RegulationProductChunking:
    """규제내용 + 제품정보 결합 청킹 전략."""
    
    def __init__(self, max_chunk_size: int = 512):
        """
        초기화.
        
        Args:
            max_chunk_size: 최대 청크 크기 (토큰 기준)
        """
        self.max_chunk_size = max_chunk_size
        from app.ai_pipeline.preprocess.semantic_chunker import SemanticChunker
        self.semantic_chunker = SemanticChunker(chunk_size=max_chunk_size)
        
    def create_combined_chunks(self, parsed_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        규제내용 + 제품정보 결합 청크 생성.
        
        Args:
            parsed_data: KTNGPDFParser에서 추출한 규제-제품 쌍 데이터
            
        Returns:
            List[Dict]: [
                {
                    "text": "결합된 텍스트",
                    "metadata": {...},
                    "chunk_type": "regulation_product_combined"
                }
            ]
        """
        logger.info(f"규제-제품 결합 청킹 시작: {len(parsed_data)}개 쌍")
        
        combined_chunks = []
        
        for idx, data in enumerate(parsed_data):
            # 결합 텍스트 생성
            combined_text = self._create_combined_text(data)
            
            # 긴 텍스트는 의미 단위로 분할
            if len(combined_text) > self.max_chunk_size * 4:  # 대략 토큰 추정
                sub_chunks = self._split_long_combined_text(combined_text, data)
                combined_chunks.extend(sub_chunks)
            else:
                # 단일 청크로 처리
                chunk = {
                    "text": combined_text,
                    "metadata": self._create_chunk_metadata(data, idx, 0),
                    "chunk_type": "regulation_product_combined",
                    "chunk_index": idx,
                    "sub_chunk_index": 0
                }
                combined_chunks.append(chunk)
        
        logger.info(f"규제-제품 결합 청킹 완료: {len(combined_chunks)}개 청크")
        return combined_chunks
    
    def _create_combined_text(self, data: Dict[str, Any]) -> str:
        """규제내용 + 제품정보를 결합한 텍스트 생성."""
        regulation_text = data.get("regulation_text", "")
        products = data.get("products", [])
        product_specs = data.get("product_specs", {})
        section = data.get("section", "")
        
        # 결합 텍스트 템플릿
        combined_parts = []
        
        # 섹션 정보
        if section:
            combined_parts.append(f"섹션: {section}")
        
        # 규제 내용
        if regulation_text:
            combined_parts.append(f"규제 내용: {regulation_text}")
        
        # 관련 제품
        if products:
            products_str = ", ".join(products)
            combined_parts.append(f"관련 제품: {products_str}")
        
        # 제품 특성
        if product_specs:
            specs_parts = []
            for key, value in product_specs.items():
                if key == "nicotine":
                    specs_parts.append(f"니코틴 함량: {value}mg")
                elif key == "battery_capacity":
                    specs_parts.append(f"배터리 용량: {value}mAh")
                elif key == "label_size":
                    specs_parts.append(f"라벨 크기: {value}cm")
                elif key == "category":
                    specs_parts.append(f"제품 카테고리: {value}")
                else:
                    specs_parts.append(f"{key}: {value}")
            
            if specs_parts:
                combined_parts.append(f"제품 특성: {', '.join(specs_parts)}")
        
        # 검색 성능 향상을 위한 키워드 강화
        keywords = self._extract_search_keywords(data)
        if keywords:
            combined_parts.append(f"관련 키워드: {', '.join(keywords)}")
        
        return "\n\n".join(combined_parts)
    
    def _extract_search_keywords(self, data: Dict[str, Any]) -> List[str]:
        """검색 성능 향상을 위한 키워드 추출."""
        keywords = set()
        
        regulation_text = data.get("regulation_text", "")
        product_specs = data.get("product_specs", {})
        
        # 규제 관련 키워드
        regulation_keywords = [
            "니코틴", "함량", "제한", "라벨", "크기", "경고", "문구",
            "배터리", "용량", "인증", "요구사항", "규제", "준수"
        ]
        
        for keyword in regulation_keywords:
            if keyword in regulation_text:
                keywords.add(keyword)
        
        # 제품 스펙 키워드
        if "category" in product_specs:
            category = product_specs["category"]
            if category == "e-cigarette":
                keywords.update(["전자담배", "베이핑", "액상"])
            elif category == "cigarette":
                keywords.update(["궐련", "담배", "연소"])
        
        # 수치 관련 키워드
        if "nicotine" in product_specs:
            keywords.add(f"{product_specs['nicotine']}mg")
        
        return list(keywords)
    
    def _split_long_combined_text(self, combined_text: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """긴 결합 텍스트를 의미 단위로 분할."""
        # 기존 SemanticChunker 활용
        chunking_result = self.semantic_chunker.chunk_document(
            combined_text, 
            {"source": "ktng_internal"}
        )
        
        sub_chunks = []
        for sub_idx, chunk in enumerate(chunking_result["chunks"]):
            sub_chunk = {
                "text": chunk["text"],
                "metadata": self._create_chunk_metadata(data, 0, sub_idx),
                "chunk_type": "regulation_product_combined_split",
                "chunk_index": 0,
                "sub_chunk_index": sub_idx
            }
            sub_chunks.append(sub_chunk)
        
        return sub_chunks
    
    def _create_chunk_metadata(self, data: Dict[str, Any], chunk_idx: int, sub_chunk_idx: int) -> Dict[str, Any]:
        """청크 메타데이터 생성."""
        product_specs = data.get("product_specs", {})
        
        metadata = {
            "meta_source": "제품-규제 (KTNG 내부대응 data).pdf",
            "meta_document_type": "internal_ktng_data",
            "meta_company": "KTNG",
            "meta_section": data.get("section", ""),
            "meta_page_number": data.get("page_number", 0),
            "meta_chunk_index": chunk_idx,
            "meta_sub_chunk_index": sub_chunk_idx,
            "meta_products": data.get("products", []),
            "meta_product_count": len(data.get("products", [])),
            "meta_chunk_type": "regulation_product_combined"
        }
        
        # 제품 스펙을 메타데이터에 추가
        if "nicotine" in product_specs:
            metadata["meta_nicotine"] = product_specs["nicotine"]
        if "battery_capacity" in product_specs:
            metadata["meta_battery_capacity"] = product_specs["battery_capacity"]
        if "label_size" in product_specs:
            metadata["meta_label_size"] = product_specs["label_size"]
        if "category" in product_specs:
            metadata["meta_category"] = product_specs["category"]
        
        return metadata