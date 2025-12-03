"""
module: hierarchy_chunker.py
description: Markdown 계층 구조 기반 청킹
author: AI Agent
created: 2025-01-14
dependencies: langchain-text-splitters, tiktoken
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class HierarchyChunker:
    """Markdown 헤더 기반 계층 청킹."""
    
    def __init__(self, max_tokens: int = 1024):
        self.max_tokens = max_tokens
        
    def chunk_document(self, markdown_text: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Markdown 텍스트를 계층 구조 기반으로 청킹.
        
        Args:
            markdown_text: Markdown 형식 텍스트
            page_num: 페이지 번호
            
        Returns:
            List[Dict]: [{"text": "...", "metadata": {...}, "hierarchy": ["Part 1", "Section 1.1"]}]
        """
        try:
            from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
            import tiktoken
        except ImportError:
            raise ImportError("langchain-text-splitters, tiktoken 설치 필요")
        
        # 1차: Markdown 헤더 기반 분할
        headers_to_split_on = [
            ("#", "Part"),
            ("##", "Section"),
            ("###", "Subsection"),
        ]
        
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_chunks = md_splitter.split_text(markdown_text)
        
        # 2차: 토큰 수 체크 및 재분할
        tokenizer = tiktoken.get_encoding("cl100k_base")
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_tokens * 4,  # 대략 4 chars = 1 token
            chunk_overlap=100,
            length_function=lambda x: len(tokenizer.encode(x))
        )
        
        final_chunks = []
        
        for idx, chunk in enumerate(md_chunks):
            text = chunk.page_content
            metadata = chunk.metadata
            
            # 토큰 수 체크
            token_count = len(tokenizer.encode(text))
            
            if token_count <= self.max_tokens:
                # 그대로 사용
                final_chunks.append({
                    "text": text,
                    "metadata": {
                        "page_num": page_num,
                        "chunk_index": len(final_chunks),
                        **metadata
                    },
                    "hierarchy": self._extract_hierarchy(metadata),
                    "token_count": token_count
                })
            else:
                # 재분할
                sub_chunks = recursive_splitter.split_text(text)
                for sub_idx, sub_text in enumerate(sub_chunks):
                    final_chunks.append({
                        "text": sub_text,
                        "metadata": {
                            "page_num": page_num,
                            "chunk_index": len(final_chunks),
                            "sub_chunk_index": sub_idx,
                            **metadata
                        },
                        "hierarchy": self._extract_hierarchy(metadata),
                        "token_count": len(tokenizer.encode(sub_text))
                    })
        
        logger.info(f"페이지 {page_num} 청킹 완료: {len(final_chunks)}개 청크")
        
        return final_chunks
    
    def _extract_hierarchy(self, metadata: Dict[str, Any]) -> List[str]:
        """메타데이터에서 계층 구조 추출."""
        hierarchy = []
        for key in ["Part", "Section", "Subsection"]:
            if key in metadata:
                hierarchy.append(metadata[key])
        return hierarchy
