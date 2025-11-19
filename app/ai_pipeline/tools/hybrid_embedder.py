# app/ai_pipeline/tools/hybrid_embedder.py

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
        self.dense_model = SentenceTransformer("BAAI/bge-m3")

    def embed(self, text: str):
        # Dense
        dense_vec = self.dense_model.encode(text).tolist()

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
