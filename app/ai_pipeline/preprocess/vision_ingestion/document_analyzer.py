"""
module: document_analyzer.py
description: 문서 첫 페이지 분석으로 규칙 파악 (능동적 전략 수립)
author: AI Agent
created: 2025-01-14
dependencies: openai
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """문서 규칙 분석 Agent."""
    
    ANALYSIS_PROMPT = """You are a regulatory document structure analyst.

Analyze the first few pages of this document and extract:

1. **Document Type**: (e.g., "US Federal Regulation", "State Law", "International Treaty")
2. **Hierarchy Pattern**: Describe the structure (e.g., "Part > Subpart > Section", "Chapter > Article")
3. **Numbering Style**: (e.g., "§ 1.1", "Article 1", "Part 123")
4. **Table Frequency**: Estimate how often tables appear (Low/Medium/High)
5. **Recommended Strategy**: Suggest optimal parsing approach

Return ONLY valid JSON:
{
  "document_type": "...",
  "hierarchy_pattern": "...",
  "numbering_style": "...",
  "table_frequency": "...",
  "recommended_strategy": "..."
}"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        
    def analyze(self, first_pages_images: list[str]) -> Dict[str, Any]:
        """
        문서 첫 페이지들을 분석하여 전략 수립.
        
        Args:
            first_pages_images: Base64 인코딩된 이미지 리스트
            
        Returns:
            Dict: 문서 분석 결과
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai가 설치되지 않았습니다")
        
        client = OpenAI(api_key=self.api_key)
        
        # 첫 페이지만 분석 (비용 절감)
        content = [
            {"type": "text", "text": "Analyze these document pages:"}
        ]
        
        for idx, img_b64 in enumerate(first_pages_images[:3]):  # 최대 3페이지
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"}
            })
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.ANALYSIS_PROMPT},
                {"role": "user", "content": content}
            ],
            max_tokens=500,
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content
        
        # JSON 파싱
        import json
        try:
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                result_text = result_text[start:end].strip()
            
            analysis = json.loads(result_text)
            logger.info(f"문서 분석 완료: {analysis.get('document_type')}")
            return analysis
            
        except json.JSONDecodeError:
            logger.warning("문서 분석 JSON 파싱 실패, 기본값 사용")
            return {
                "document_type": "Unknown",
                "hierarchy_pattern": "Standard",
                "numbering_style": "Numeric",
                "table_frequency": "Medium",
                "recommended_strategy": "Use default Vision pipeline"
            }
