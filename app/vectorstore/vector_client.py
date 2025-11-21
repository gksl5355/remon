"""
module: vector_client.py
description: Qdrant VectorDB 클라이언트 (하이브리드 서칭: dense + sparse)
author: AI Agent
created: 2025-11-12
updated: 2025-01-18
dependencies:
    - qdrant-client>=1.15.1
    - app.config.settings
"""

import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    SparseVector,
    SparseVectorParams,
)
import os

logger = logging.getLogger(__name__)

# settings.py 통합 (환경변수 폴백)
try:
    from app.config.settings import settings
    QDRANT_HOST = (
        getattr(settings, "QDRANT_URL", "http://localhost:6333")
        .replace("http://", "")
        .replace("https://", "")
        .split(":")[0]
    )
    QDRANT_PORT = 6333
    QDRANT_COLLECTION = getattr(settings, "QDRANT_COLLECTION", "remon_regulations")
    QDRANT_PATH = getattr(settings, "QDRANT_PATH", "./data/qdrant")
    QDRANT_USE_LOCAL = os.getenv("QDRANT_USE_LOCAL", "false").lower() == "true"
except ImportError:
    logger.warning("settings.py 로드 실패, 환경변수 사용")
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "remon_regulations")
    QDRANT_PATH = os.getenv("QDRANT_PATH", "./data/qdrant")
    QDRANT_USE_LOCAL = os.getenv("QDRANT_USE_LOCAL", "false").lower() == "true"


class VectorClient:
    """
    Qdrant VectorDB 클라이언트 (하이브리드 서칭 지원).

    특징:
    - Dense vector (BGE-M3 1024차원) + Sparse vector (BM25 스타일) 동시 저장
    - 하이브리드 검색: 의미 검색 + 키워드 검색 결합
    - 메타데이터 필터링 (국가, 규제 타입 등)
    - 로컬/원격 모드 지원
    """

    def __init__(
        self, collection_name: str = QDRANT_COLLECTION, use_local: bool = None
    ):
        """
        Qdrant 클라이언트 초기화.

        Args:
            collection_name: 컬렉션 이름
            use_local: True면 로컬 저장소, False면 원격 서버, None이면 환경변수 사용
        """
        self.collection_name = collection_name

        if use_local is None:
            use_local = QDRANT_USE_LOCAL

        if use_local:
            self.client = QdrantClient(path=QDRANT_PATH)
            logger.info(f"✅ Qdrant 로컬 모드: {QDRANT_PATH}")
        else:
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            logger.info(f"✅ Qdrant 서버 모드: {QDRANT_HOST}:{QDRANT_PORT}")

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """컬렉션 생성 (없으면)."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(size=1024, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )
            logger.info(f"✅ 컬렉션 생성: {self.collection_name}")
        else:
            logger.info(f"✅ 컬렉션 존재: {self.collection_name}")

    def insert(
        self,
        texts: List[str],
        dense_embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        sparse_embeddings: Optional[List[Dict[int, float]]] = None,
        batch_size: int = 100,
    ) -> None:
        """
        문서 삽입 (dense + sparse) - 배치 처리.

        Args:
            texts: 문서 텍스트 리스트
            dense_embeddings: Dense 벡터 (1024차원)
            metadatas: 메타데이터
            sparse_embeddings: Sparse 벡터 (선택)
            batch_size: 배치 크기
        """
        import uuid

        total = len(texts)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            points = []

            for idx in range(batch_start, batch_end):
                text = texts[idx]
                dense = dense_embeddings[idx]
                meta = metadatas[idx]

                point_id = str(uuid.uuid4())
                vectors = {"dense": dense}

                if sparse_embeddings and idx < len(sparse_embeddings):
                    sparse = sparse_embeddings[idx]
                    vectors["sparse"] = SparseVector(
                        indices=list(sparse.keys()),
                        values=list(sparse.values()),
                    )

                payload = {"text": text, **meta}

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vectors,
                        payload=payload,
                    )
                )

            self.client.upsert(
                collection_name=self.collection_name, points=points, wait=True
            )
            logger.info(
                f"  ✅ 배치 {batch_start//batch_size + 1}/{(total + batch_size - 1)//batch_size}: {len(points)}개 삽입"
            )

        logger.info(f"✅ 총 {total}개 문서 삽입 완료")

    def search(
        self,
        query_dense: List[float],
        query_sparse: Optional[Dict[int, float]] = None,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        hybrid_alpha: float = 0.7,
    ) -> Dict[str, Any]:
        """
        하이브리드 검색 (dense + sparse).

        Args:
            query_dense: Dense 쿼리 벡터
            query_sparse: Sparse 쿼리 벡터 (선택)
            top_k: 반환 개수
            filters: 메타데이터 필터
            hybrid_alpha: Dense 가중치 (0~1)

        Returns:
            검색 결과 딕셔너리
        """
        qdrant_filter = self._build_qdrant_filter(filters)
        
        # Dense 검색
        dense_results = list(
            self.client.query_points(
                collection_name=self.collection_name,
                query=query_dense,
                using="dense",
                limit=top_k,
                with_payload=True,
                query_filter=qdrant_filter,
            )
        )
        
        # Sparse 없으면 Dense만 반환
        if not query_sparse:
            return {
                "ids": [r.id for r in dense_results],
                "documents": [r.payload.get("text", "") for r in dense_results],
                "metadatas": [r.payload for r in dense_results],
                "scores": [r.score for r in dense_results],
            }
        
        # Sparse 검색
        sparse_vector = SparseVector(
            indices=list(query_sparse.keys()),
            values=list(query_sparse.values()),
        )
        sparse_results = list(
            self.client.query_points(
                collection_name=self.collection_name,
                query=sparse_vector,
                using="sparse",
                limit=top_k,
                with_payload=True,
                query_filter=qdrant_filter,
            )
        )

        return self._combine_results(
            [dense_results, sparse_results], hybrid_alpha, top_k
        )

    def _combine_results(
        self, batch_results: List[List], alpha: float, top_k: int
    ) -> Dict[str, Any]:
        """하이브리드 결과 결합 (RRF)."""
        dense_results, sparse_results = batch_results

        scores = {}
        payloads = {}
        dense_scores = {}
        sparse_scores = {}

        for rank, result in enumerate(dense_results, 1):
            rrf_score = alpha * (1 / (rank + 60))
            scores[result.id] = scores.get(result.id, 0) + rrf_score
            dense_scores[result.id] = result.score
            payloads[result.id] = result.payload

        for rank, result in enumerate(sparse_results, 1):
            rrf_score = (1 - alpha) * (1 / (rank + 60))
            scores[result.id] = scores.get(result.id, 0) + rrf_score
            sparse_scores[result.id] = result.score
            if result.id not in payloads:
                payloads[result.id] = result.payload

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[
            :top_k
        ]

        final_metadatas = []
        for doc_id in sorted_ids:
            metadata = payloads[doc_id].copy()
            metadata["_dense_score"] = dense_scores.get(doc_id)
            metadata["_sparse_score"] = sparse_scores.get(doc_id)
            final_metadatas.append(metadata)

        return {
            "ids": sorted_ids,
            "documents": [payloads[id].get("text", "") for id in sorted_ids],
            "metadatas": final_metadatas,
            "scores": [scores[id] for id in sorted_ids],
        }

    def delete_collection(self) -> None:
        """컬렉션 삭제."""
        self.client.delete_collection(collection_name=self.collection_name)
        logger.info(f"✅ 컬렉션 삭제: {self.collection_name}")

    def _build_qdrant_filter(self, filters: Optional[Dict[str, Any]]):
        """Dict 필터 → Qdrant Filter 변환."""
        if not filters:
            return None

        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        conditions = []

        for key, value in filters.items():
            if key.endswith("_from"):
                field = key.replace("_from", "")
                conditions.append(FieldCondition(key=field, range=Range(gte=value)))
            elif key.endswith("_to"):
                field = key.replace("_to", "")
                conditions.append(FieldCondition(key=field, range=Range(lte=value)))
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

        return Filter(must=conditions) if conditions else None

    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회."""
        info = self.client.get_collection(collection_name=self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "vectors_config": str(info.config.params.vectors),
        }
