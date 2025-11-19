# app/ai_pipeline/tools/hybrid_retriever.py

from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector
from .hybrid_embedder import HybridEmbedder


class HybridRetriever:
    """
    단순화된 Hybrid Retriever
    - dense (BGE-M3)
    - sparse (BoW 50k)
    - Qdrant hybrid 검색(dense + sparse fusion)
    """

    def __init__(
        self,
        default_collection: str,
        host: str = "localhost",
        port: int = 6333,
    ):
        # HTTP REST Client 사용 (search 지원)
        self.client = QdrantClient(url=f"http://{host}:{port}")

        self.default_collection = default_collection
        self.embedder = HybridEmbedder()

    # ----------------------------------------------------
    # Hybrid 검색
    # ----------------------------------------------------
    def search(
        self,
        query: str,
        collection: str = None,
        limit: int = 5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        """
        Hybrid 검색
        - dense, sparse 임베딩 생성
        - 각각 Qdrant에서 검색
        - score fusion 후 상위 limit 반환
        """
        collection_name = collection or self.default_collection
        if not collection_name:
            raise ValueError("Collection name must be provided.")

        # 1) 임베딩 생성
        emb = self.embedder.embed(query)
        dense_vec = emb["dense"]
        sparse_vec: SparseVector = emb["sparse"]

        # 2) Dense 검색
        dense_results = self.client.search(
            collection_name=collection_name,
            query_vector={"name": "dense", "vector": dense_vec},
            limit=limit * 3,
        )

        # 3) Sparse 검색
        sparse_results = self.client.search(
            collection_name=collection_name,
            query_vector={"name": "sparse", "vector": sparse_vec},
            limit=limit * 3,
        )

        # 4) 점수 결합(fusion)
        score_map = {}
        for r in dense_results:
            score_map.setdefault(
                r.id, {"payload": r.payload, "dense": 0.0, "sparse": 0.0}
            )
            score_map[r.id]["dense"] = r.score

        for r in sparse_results:
            score_map.setdefault(
                r.id, {"payload": r.payload, "dense": 0.0, "sparse": 0.0}
            )
            score_map[r.id]["sparse"] = r.score

        # Fusion
        fused = []
        for pid, entry in score_map.items():
            fused_score = (
                entry["dense"] * dense_weight
                + entry["sparse"] * sparse_weight
            )
            fused.append({
                "id": pid,
                "score": fused_score,
                "payload": entry["payload"],
            })

        # 상위 limit 반환
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:limit]