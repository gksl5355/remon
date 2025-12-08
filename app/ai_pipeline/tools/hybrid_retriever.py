# app/ai_pipeline/tools/hybrid_retriever.py

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

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
        url: str | None = None,
        api_key: str | None = None,
        prefer_grpc: bool = False,
        timeout: float = 10.0,
        vector_name: str = "strategy-dense-vector",
    ):
        resolved_url = url or f"http://{host}:{port}"
        self.client = QdrantClient(
            url=resolved_url,
            api_key=api_key,
            prefer_grpc=False,  # hybrid(gRPC) 비활성
            timeout=timeout,
        )

        self.default_collection = default_collection
        self.vector_name = vector_name
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
        Dense-only 검색. 메타데이터 필터 적용.
        """
        collection_name = collection or self.default_collection
        if not collection_name:
            raise ValueError("Collection name must be provided.")

        # 1) 임베딩 생성 (dense만 사용)
        emb = self.embedder.embed(query)
        dense_vec = emb["dense"]

        # 2) Dense 검색
        qdrant_filter = self._build_query_filter(filters)

        dense_response = self.client.query_points(
            collection_name=collection_name,
            query=dense_vec,
            using=self.vector_name,
            limit=limit * 3,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        dense_results = dense_response.points or []
        fused: List[Dict[str, Any]] = []
        for r in dense_results:
            fused.append(
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload,
                    "text": r.payload.get("text", ""),
                    "scores": {
                        "dense_score": r.score,
                        "sparse_score": 0.0,
                        "final_score": r.score,
                    },
                }
            )

        fused.sort(key=lambda x: x["scores"].get("final_score", 0.0), reverse=True)
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
