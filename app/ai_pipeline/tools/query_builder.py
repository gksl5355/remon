"""
module: query_builder.py
description: 피처별 검색 쿼리 생성 (LLM 기반)
author: AI Agent
created: 2025-01-22
updated: 2025-01-22
dependencies:
    - openai
"""

import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class QueryBuilder:
    """피처별 검색 쿼리 생성기."""
    
    def __init__(self, llm_client: Optional[AsyncOpenAI] = None):
        self.llm = llm_client or AsyncOpenAI()
    
    async def build_query(
        self,
        feature_name: str,
        feature_value: Any,
        feature_unit: Optional[str] = None,
        change_hints: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        피처 정보와 변경 힌트를 기반으로 검색 쿼리 생성.
        
        Args:
            feature_name: 피처명 (예: "nicotine")
            feature_value: 피처값 (예: "20mg/g")
            feature_unit: 단위 (예: "mg/g")
            change_hints: 변경 감지 힌트 (keywords, numerical_changes 등)
        
        Returns:
            검색 쿼리 문자열
        """
        # 기본 쿼리
        base_parts = [feature_name]
        if feature_value:
            base_parts.append(str(feature_value))
        
        # 변경 힌트 추가
        hint_keywords = []
        if change_hints:
            hint_keywords.extend(change_hints.get("keywords", [])[:3])
            for num_change in change_hints.get("numerical_changes", [])[:2]:
                if num_change.get("field") == feature_name:
                    hint_keywords.append(str(num_change.get("new_value", "")))
        
        # LLM 프롬프트
        prompt = f"""Generate a concise search query for regulatory documents.

Feature: {feature_name}
Value: {feature_value}
Unit: {feature_unit or "N/A"}
Change hints: {", ".join(hint_keywords) if hint_keywords else "None"}

Return ONLY the search query (max 10 words), no explanation."""

        try:
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You generate search queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=50
            )
            
            query = response.choices[0].message.content.strip()
            logger.debug(f"Query generated: {query}")
            return query
            
        except Exception as e:
            logger.warning(f"Query generation failed: {e}, using fallback")
            # Fallback: 기본 조합
            return " ".join(base_parts + hint_keywords[:2])
