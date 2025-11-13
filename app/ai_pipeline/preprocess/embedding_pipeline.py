"""
module: embedding_pipeline.py
description: BGE-M3 기반 임베딩 생성 및 관리 (Chroma VectorDB 연동 예비)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger, app.ai_pipeline.preprocess.config
    - sentence-transformers (BGE-M3)
    - numpy, typing
"""

from typing import List, Dict, Tuple, Optional, Any
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# BGE-M3 임베딩 모델 (FlagEmbedding 우선, sentence-transformers 폴백)
try:
    from FlagEmbedding import BGEM3FlagModel
    HAS_FLAG_EMBEDDING = True
    HAS_SENTENCE_TRANSFORMERS = False
except ImportError:
    HAS_FLAG_EMBEDDING = False
    try:
        from sentence_transformers import SentenceTransformer
        HAS_SENTENCE_TRANSFORMERS = True
    except ImportError:
        HAS_SENTENCE_TRANSFORMERS = False
        logger.warning("⚠️ FlagEmbedding 또는 sentence-transformers 설치 필요")


class EmbeddingPipeline:
    """
    BGE-M3 모델을 사용하여 텍스트를 임베딩으로 변환하는 클래스.
    
    역할:
    - BGE-M3 모델 로드 (1024차원 벡터)
    - 배치 임베딩 (효율적인 처리)
    - 임베딩 정규화 (cosine 유사도 계산용)
    - 메타데이터와 함께 Chroma 연동 준비
    
    특징:
    - 다언어 지원 (한글, 영문, 중문, 일문 등)
    - FP16 정밀도 지원 (메모리 절약)
    - 캐싱 (중복 임베딩 방지)
    - 배치 처리 (대규모 문서 효율 처리)
    """
    
    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool = True, batch_size: int = 32, use_sparse: bool = True):
        """
        임베딩 파이프라인 초기화.
        
        Args:
            model_name (str): Hugging Face 모델명. 기본값: "BAAI/bge-m3"
            use_fp16 (bool): FP16 정밀도 사용 (메모리 절약). 기본값: True
            batch_size (int): 배치 크기. 기본값: 32
            use_sparse (bool): Sparse vector 사용 (FlagEmbedding 필요). 기본값: True
        """
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self.use_sparse = use_sparse and HAS_FLAG_EMBEDDING
        self.model = None
        self.embedding_cache: Dict[str, Dict] = {}  # 캐시 (dense + sparse)
        
        if HAS_FLAG_EMBEDDING or HAS_SENTENCE_TRANSFORMERS:
            self._load_model()
        else:
            logger.warning("⚠️ 임베딩 라이브러리 미설치. 기능 미지원")
        
        logger.info(
            f"✅ EmbeddingPipeline 초기화: model={model_name}, "
            f"fp16={use_fp16}, batch_size={batch_size}, sparse={self.use_sparse}"
        )
    
    def _load_model(self) -> None:
        """BGE-M3 모델 로드 (FlagEmbedding 우선)."""
        try:
            if HAS_FLAG_EMBEDDING and self.use_sparse:
                self.model = BGEM3FlagModel(self.model_name, use_fp16=self.use_fp16)
                logger.info(f"✅ 모델 로드 완료 (FlagEmbedding): {self.model_name}")
            elif HAS_SENTENCE_TRANSFORMERS:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                self.use_sparse = False  # sentence-transformers는 sparse 미지원
                logger.info(f"✅ 모델 로드 완료 (SentenceTransformer): {self.model_name}")
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            raise RuntimeError(f"BGE-M3 모델 로드 실패: {e}")
    
    def embed_texts(self, texts: List[str], normalize: bool = True) -> Dict[str, Any]:
        """
        텍스트 리스트를 임베딩으로 변환합니다 (Qdrant 하이브리드 서칭 지원).
        
        Args:
            texts (List[str]): 임베딩할 텍스트 리스트
            normalize (bool): 임베딩 정규화 (cosine 유사도용). 기본값: True
        
        Returns:
            Dict[str, Any]: {
                "dense": List[List[float]] (N x 1024),
                "sparse": List[Dict[int, float]] (선택적, use_sparse=True 시)
            }
        
        Raises:
            RuntimeError: 모델이 로드되지 않은 경우
            ValueError: 텍스트 리스트가 비어있는 경우
        """
        if self.model is None:
            raise RuntimeError("모델 미로드")
        
        if not texts:
            raise ValueError("텍스트 리스트가 비어있습니다")
        
        # 캐시 히트 확인
        uncached_texts = []
        uncached_indices = []
        dense_embeddings = [None] * len(texts)
        sparse_embeddings = [None] * len(texts) if self.use_sparse else None
        
        for idx, text in enumerate(texts):
            if text in self.embedding_cache:
                cached = self.embedding_cache[text]
                dense_embeddings[idx] = cached["dense"]
                if self.use_sparse:
                    sparse_embeddings[idx] = cached.get("sparse")
            else:
                uncached_texts.append(text)
                uncached_indices.append(idx)
        
        # 캐시되지 않은 텍스트 임베딩
        if uncached_texts:
            logger.debug(f"임베딩 생성 중: {len(uncached_texts)}개 텍스트")
            
            if HAS_FLAG_EMBEDDING and self.use_sparse:
                # FlagEmbedding: dense + sparse
                embeddings_dict = self.model.encode(
                    uncached_texts,
                    batch_size=self.batch_size,
                    max_length=8192,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False
                )
                
                for idx, text in enumerate(uncached_texts):
                    dense = embeddings_dict['dense_vecs'][idx]
                    sparse = embeddings_dict['lexical_weights'][idx]  # Dict[int, float]
                    
                    self.embedding_cache[text] = {"dense": dense, "sparse": sparse}
                    dense_embeddings[uncached_indices[idx]] = dense
                    sparse_embeddings[uncached_indices[idx]] = sparse
            
            else:
                # SentenceTransformer: dense only
                for i in range(0, len(uncached_texts), self.batch_size):
                    batch = uncached_texts[i:i + self.batch_size]
                    batch_embeddings = self.model.encode(
                        batch,
                        convert_to_numpy=True,
                        normalize_embeddings=normalize,
                        show_progress_bar=False,
                    )
                    
                    for j, text in enumerate(batch):
                        dense = batch_embeddings[j]
                        self.embedding_cache[text] = {"dense": dense}
                        dense_embeddings[uncached_indices[i + j]] = dense
        
        # Qdrant 호환 형식으로 반환 (List[List[float]])
        result = {
            "dense": [emb.tolist() if isinstance(emb, np.ndarray) else emb for emb in dense_embeddings]
        }
        
        if self.use_sparse and sparse_embeddings:
            result["sparse"] = sparse_embeddings  # List[Dict[int, float]]
        
        logger.info(
            f"✅ 임베딩 생성 완료: {len(texts)}개 텍스트, "
            f"캐시 히트율 {(len(texts) - len(uncached_texts)) / len(texts) * 100:.1f}%"
        )
        
        return result
    
    def embed_single_text(self, text: str, normalize: bool = True) -> Dict[str, Any]:
        """
        단일 텍스트를 임베딩으로 변환합니다.
        
        Args:
            text (str): 임베딩할 텍스트
            normalize (bool): 정규화 여부. 기본값: True
        
        Returns:
            Dict[str, Any]: {"dense": np.ndarray, "sparse": Dict (선택적)}
        """
        embeddings = self.embed_texts([text], normalize=normalize)
        result = {"dense": embeddings["dense"][0]}
        if "sparse" in embeddings:
            result["sparse"] = embeddings["sparse"][0]
        return result
    
    def batch_embed_documents(
        self, documents: List[Dict[str, Any]], text_field: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        여러 문서를 임베딩으로 변환하고 메타데이터와 함께 반환합니다.
        
        Args:
            documents (List[Dict[str, Any]]): 
                [
                    {
                        "id": "doc_1",
                        "text": "문서 텍스트",
                        "metadata": {...}
                    },
                    ...
                ]
            text_field (str): 텍스트 필드명. 기본값: "text"
        
        Returns:
            List[Dict[str, Any]]: 
                [
                    {
                        "id": "doc_1",
                        "text": "문서 텍스트",
                        "embedding": [0.1, 0.2, ...],  # 1024차원 벡터
                        "metadata": {...}
                    },
                    ...
                ]
        """
        texts = [doc.get(text_field, "") for doc in documents]
        embeddings = self.embed_texts(texts)
        
        results = []
        for doc, embedding in zip(documents, embeddings):
            results.append({
                "id": doc.get("id"),
                "text": doc.get(text_field, ""),
                "embedding": embedding.tolist(),  # numpy → list
                "metadata": doc.get("metadata", {}),
            })
        
        logger.info(f"✅ {len(results)}개 문서 임베딩 배치 처리 완료")
        return results
    
    def similarity_search(
        self, query_text: str, candidates: List[str], top_k: int = 5
    ) -> List[Tuple[int, float, str]]:
        """
        쿼리 텍스트와 후보 텍스트들의 유사도를 계산합니다.
        
        Args:
            query_text (str): 쿼리 텍스트
            candidates (List[str]): 후보 텍스트 리스트
            top_k (int): 상위 K개 반환. 기본값: 5
        
        Returns:
            List[Tuple[int, float, str]]: [(인덱스, 점수, 텍스트), ...]
                점수는 0~1 사이의 cosine 유사도
        """
        if not candidates:
            return []
        
        # 임베딩
        query_embedding = self.embed_single_text(query_text, normalize=True)
        candidate_embeddings = self.embed_texts(candidates, normalize=True)
        
        # Cosine 유사도 계산
        similarities = []
        for idx, cand_emb in enumerate(candidate_embeddings):
            # 정규화된 임베딩: cosine_similarity = dot product
            score = float(np.dot(query_embedding, cand_emb))
            similarities.append((idx, score, candidates[idx]))
        
        # 상위 K개 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = similarities[:top_k]
        
        logger.debug(f"유사도 검색 완료: 상위 {len(results)}개 결과")
        return results
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """캐시 통계를 반환합니다."""
        cache_size = len(self.embedding_cache)
        cache_memory_mb = (cache_size * 1024 * 4) / (1024 * 1024)  # 1024차원 float32
        
        return {
            "cache_size": cache_size,
            "cache_memory_mb": round(cache_memory_mb, 2),
            "model_name": self.model_name,
            "embedding_dimension": 1024,
        }
    
    def clear_cache(self) -> None:
        """캐시를 비웁니다."""
        self.embedding_cache.clear()
        logger.info("✅ 임베딩 캐시 초기화")
