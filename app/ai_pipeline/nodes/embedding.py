"""
module: embedding.py
description: 임베딩 노드 - 변경 감지 결과에 따라 Dual Indexing 수행
author: AI Agent
created: 2025-01-21
updated: 2025-01-21
dependencies:
    - app.ai_pipeline.state
    - app.ai_pipeline.preprocess.semantic_processing
"""

import logging
from pathlib import Path

from app.ai_pipeline.state import AppState

logger = logging.getLogger(__name__)


async def embedding_node(state: AppState) -> AppState:
    """
    임베딩 노드: 변경 감지 결과에 따라 임베딩 수행.
    
    실행 조건:
    - state["needs_embedding"] = True (변경 감지 또는 신규 규제)
    
    처리 내용:
    - Qdrant VectorDB에 청크 임베딩 저장
    - Knowledge Graph에 엔티티/관계 저장
    """
    logger.info("📦 Embedding Node 시작")
    
    preprocess_results = state.get("preprocess_results", [])
    if not preprocess_results:
        logger.warning("⚠️ preprocess_results 없음 - 임베딩 스킵")
        return state
    
    result = preprocess_results[0]
    chunks = result.get("chunks", [])
    graph_data = result.get("graph_data", {"nodes": [], "edges": []})
    vision_results = result.get("vision_extraction_result", [])
    
    if not chunks:
        logger.warning("⚠️ chunks 없음 - 임베딩 스킵")
        return state
    
    # Dual Indexing 실행
    from app.ai_pipeline.preprocess.semantic_processing import DualIndexer
    
    indexer = DualIndexer()
    regulation_id = result.get("regulation_id")
    pdf_path = result.get("pdf_path", "unknown.pdf")
    
    index_summary = indexer.index(
        chunks=chunks,
        graph_data=graph_data,
        source_file=Path(pdf_path).name,
        regulation_id=regulation_id,
        vision_results=vision_results
    )
    
    state["dual_index_summary"] = index_summary
    logger.info(f"✅ 임베딩 완료: {index_summary.get('qdrant_chunks', 0)}개 청크")
    
    return state


__all__ = ["embedding_node"]
