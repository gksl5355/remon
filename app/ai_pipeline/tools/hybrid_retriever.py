# app/ai_pipeline/tools/hybrid_retriever.py

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
)

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
        collection: str | None = None,
        limit: int = 5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
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
        qdrant_filter = self._build_query_filter(filters)

        dense_response = self.client.query_points(
            collection_name=collection_name,
            query=dense_vec,
            using="dense",
            limit=limit * 3,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        dense_results = dense_response.points or []

        # 3) Sparse 검색
        sparse_response = self.client.query_points(
            collection_name=collection_name,
            query=sparse_vec,
            using="sparse",
            limit=limit * 3,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        sparse_results = sparse_response.points or []

        # 4) 점수 결합(fusion)
        score_map: Dict[str, Dict[str, Any]] = {}
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
        fused: List[Dict[str, Any]] = []
        for pid, entry in score_map.items():
            fused_score = (
                entry["dense"] * dense_weight
                + entry["sparse"] * sparse_weight
            )
            fused.append({
                "id": pid,
                "score": fused_score,
                "payload": entry["payload"],
                "text": entry["payload"].get("text", ""),
                "scores": {
                    "dense_score": entry["dense"],
                    "sparse_score": entry["sparse"],
                    "final_score": fused_score,
                },
            })

        # 상위 limit 반환
        fused.sort(
            key=lambda x: x["scores"].get("final_score", 0.0),
            reverse=True,
        )
        return fused[:limit]
    
    def _build_query_filter(
        self,
        filters: Optional[Dict[str, Any]],
    ) -> Optional[Filter]:
        """Dict 형태의 필터를 Qdrant Filter 객체로 변환한다."""
        if not filters:
            return None

        conditions = []
        for key, value in filters.items():
            if value is None:
                continue

            if key.endswith("_from"):
                field = key[:-5]
                conditions.append(FieldCondition(key=field, range=Range(gte=value)))
            elif key.endswith("_to"):
                field = key[:-3]
                conditions.append(FieldCondition(key=field, range=Range(lte=value)))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        return Filter(must=conditions) if conditions else None
