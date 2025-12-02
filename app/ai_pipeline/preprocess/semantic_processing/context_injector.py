"""
module: context_injector.py
description: 청크에 부모 계층 정보 주입
author: AI Agent
created: 2025-01-14
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContextInjector:
    """청크에 계층 컨텍스트 주입."""
    
    def inject_context(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        청크 텍스트 앞에 계층 정보 추가.
        
        Args:
            chunks: HierarchyChunker 출력
            
        Returns:
            List[Dict]: 컨텍스트가 주입된 청크
        """
        enriched_chunks = []
        
        for chunk in chunks:
            hierarchy = chunk.get("hierarchy", [])
            original_text = chunk["text"]
            
            # 계층 경로 생성
            if hierarchy:
                context_prefix = " > ".join(hierarchy) + "\n\n"
                enriched_text = context_prefix + original_text
            else:
                enriched_text = original_text
            
            enriched_chunk = chunk.copy()
            enriched_chunk["text"] = enriched_text
            enriched_chunk["original_text"] = original_text
            
            enriched_chunks.append(enriched_chunk)
        
        logger.debug(f"컨텍스트 주입 완료: {len(enriched_chunks)}개 청크")
        
        return enriched_chunks
