"""
module: embedding_pipeline.py
description: BGE-M3 임베딩 생성 (Dense + Sparse)
author: AI Agent
created: 2025-01-14
dependencies: FlagEmbedding, sentence-transformers
"""

from typing import List, Dict, Any
import logging
import numpy as np

logger = logging.getLogger(__name__)

try:
    from FlagEmbedding import BGEM3FlagModel
    HAS_FLAG_EMBEDDING = True
except ImportError:
    HAS_FLAG_EMBEDDING = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class EmbeddingPipeline:
    """BGE-M3 임베딩 생성."""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool = True, batch_size: int = 32, use_sparse: bool = True):
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self.use_sparse = use_sparse and HAS_FLAG_EMBEDDING
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        if HAS_FLAG_EMBEDDING and self.use_sparse:
            self.model = BGEM3FlagModel(self.model_name, use_fp16=self.use_fp16)
            logger.info(f"✅ FlagEmbedding 로드: {self.model_name}")
        elif HAS_SENTENCE_TRANSFORMERS:
            self.model = SentenceTransformer(self.model_name)
            self.use_sparse = False
            logger.info(f"✅ SentenceTransformer 로드: {self.model_name}")
        else:
            raise RuntimeError("FlagEmbedding 또는 sentence-transformers 필요")
    
    def embed_texts(self, texts: List[str]) -> Dict[str, Any]:
        if not texts:
            raise ValueError("텍스트 리스트 비어있음")
        
        if HAS_FLAG_EMBEDDING and self.use_sparse:
            embeddings_dict = self.model.encode(
                texts,
                batch_size=self.batch_size,
                max_length=8192,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False
            )
            
            result = {
                "dense": [emb.tolist() if isinstance(emb, np.ndarray) else emb for emb in embeddings_dict['dense_vecs']],
                "sparse": embeddings_dict['lexical_weights']
            }
        else:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=self.batch_size
            )
            result = {"dense": [emb.tolist() for emb in embeddings]}
        
        logger.info(f"✅ 임베딩 완료: {len(texts)}개")
        return result
    
    def embed_single_text(self, text: str) -> Dict[str, Any]:
        embeddings = self.embed_texts([text])
        result = {"dense": embeddings["dense"][0]}
        if "sparse" in embeddings:
            result["sparse"] = embeddings["sparse"][0]
        return result
