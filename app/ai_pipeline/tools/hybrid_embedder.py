# app/ai_pipeline/tools/hybrid_embedder.py

import os
import hashlib
from sentence_transformers import SentenceTransformer
from qdrant_client.models import SparseVector
from collections import Counter


class HybridEmbedder:
    """
    Dense + Sparse Hybrid Embedding
    - BGE-M3 기반 Dense
    - 단순 BoW 기반 Sparse (50k dimensions hashing)
    """

    def __init__(self):
        use_dummy = os.getenv("USE_DUMMY_EMBEDDING", "true").lower() != "false"
        if use_dummy:
            self.dense_model = None
        else:
            try:
                self.dense_model = SentenceTransformer("BAAI/bge-m3")
            except Exception:
                # 네트워크/모델 로드 실패 시 백업용 더미 임베더 사용
                self.dense_model = None

    def embed(self, text: str):
        # Dense
        if self.dense_model:
            dense_vec = self.dense_model.encode(text).tolist()
        else:
            # deterministic pseudo-embedding for offline mode
            h = hashlib.sha256(text.encode("utf-8")).digest()
            dense_vals = [(b / 255.0) for b in h]
            # repeat to 1024 dims
            dense_vec = (dense_vals * (1024 // len(dense_vals) + 1))[:1024]

        # Sparse
        tokens = text.lower().split()
        bow = Counter(tokens)

        indices = []
        values = []

        for word, freq in bow.items():
            idx = abs(hash(word)) % 50000
            indices.append(idx)
            values.append(float(freq))

        sparse = SparseVector(indices=indices, values=values)

        return {
            "dense": dense_vec,
            "sparse": sparse
        }
