"""Hybrid vector client utilities backed by Qdrant.

This module centralises the logic for generating dense+sparse BGE-M3 embeddings,
inserting them into Qdrant, and querying results that map nicely into the
LangGraph map_products node."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from sentence_transformers import SentenceTransformer

try:  # Optional - 고품질 하이브리드 임베딩
    from FlagEmbedding import BGEM3FlagModel  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    BGEM3FlagModel = None  # type: ignore

from app.config.settings import settings
from app.vectorstore.vector_schema import SparseVectorPayload

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9가-힣]+")
SPARSE_HASH_SPACE = 2**31 - 1


@dataclass
class HybridEmbedding:
    dense: List[float]
    sparse: SparseVectorPayload | None = None


@dataclass
class VectorMatch:
    id: str
    payload: Dict[str, Any]
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None


@dataclass
class VectorConfig:
    url: str
    collection_name: str
    api_key: str | None = None
    prefer_grpc: bool = False
    timeout: float = 10.0


class HybridEmbedder:
    """BGE-M3 하이브리드 임베딩 헬퍼 (dense + sparse)."""

    _flag_model: Any | None = None
    _sentence_model: SentenceTransformer | None = None

    @classmethod
    def encode(cls, text: str) -> HybridEmbedding:
        text = text or ""
        if BGEM3FlagModel is not None:
            return cls._encode_with_flag_embedding(text)
        return cls._encode_with_sentence_transformers(text)

    @classmethod
    def _encode_with_flag_embedding(cls, text: str) -> HybridEmbedding:
        if cls._flag_model is None:
            logger.info("Loading BGEM3FlagModel for hybrid embeddings (dense+sparse).")
            cls._flag_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

        outputs = cls._flag_model.encode(
            [text],
            return_dense=True,
            return_sparse=True,
            normalize_to_unit=True,
        )
        dense_vec = outputs["dense_vecs"][0]
        sparse_vec = outputs["sparse_vecs"][0]
        return HybridEmbedding(
            dense=[float(v) for v in dense_vec],
            sparse=SparseVectorPayload(
                indices=[int(i) for i in sparse_vec["indices"]],
                values=[float(v) for v in sparse_vec["values"]],
            ),
        )

    @classmethod
    def _encode_with_sentence_transformers(cls, text: str) -> HybridEmbedding:
        if cls._sentence_model is None:
            logger.info(
                "Loading SentenceTransformer(BAAI/bge-m3) for dense embeddings."
            )
            cls._sentence_model = SentenceTransformer("BAAI/bge-m3")

        dense_vec = cls._sentence_model.encode(
            text, normalize_embeddings=True, convert_to_numpy=True
        )
        sparse = cls._build_sparse_payload(text)
        return HybridEmbedding(
            dense=dense_vec.tolist(),
            sparse=sparse,
        )

    @staticmethod
    def _build_sparse_payload(text: str) -> SparseVectorPayload | None:
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return None
        counts = Counter(tokens)
        indices: List[int] = []
        values: List[float] = []
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest()
            indices.append(int(digest, 16) % SPARSE_HASH_SPACE)
            values.append(float(count))
        return SparseVectorPayload(indices=indices, values=values).sort()


class VectorClient:
    """Qdrant vector store wrapper (dense + sparse hybrid)."""

    def __init__(self, client: QdrantClient, config: VectorConfig):
        self.client = client
        self.config = config

    @classmethod
    def from_settings(cls, cfg: VectorConfig | None = None) -> "VectorClient":
        cfg = cfg or VectorConfig(
            url=settings.QDRANT_URL,
            collection_name=settings.QDRANT_COLLECTION,
            api_key=settings.QDRANT_API_KEY,
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
            timeout=settings.QDRANT_TIMEOUT,
        )
        client = QdrantClient(
            url=cfg.url,
            api_key=cfg.api_key,
            prefer_grpc=cfg.prefer_grpc,
            timeout=cfg.timeout,
        )
        return cls(client, cfg)

    async def insert(
        self,
        texts: Sequence[str],
        embeddings: Sequence[Sequence[float]] | None,
        metadatas: Sequence[Dict[str, Any]],
        sparse_embeddings: (
            Sequence[SparseVectorPayload | Dict[str, Any] | None] | None
        ) = None,
        ids: Sequence[str | int] | None = None,
    ) -> None:
        """Insert dense+sparse vectors into Qdrant.

        If either dense or sparse embeddings are missing, the method generates
        them using :class:`HybridEmbedder`.

        Args:
            texts: Raw texts corresponding to `metadatas`.
            embeddings: Optional dense embeddings aligned with `texts`.
            metadatas: Qdrant payloads (must include `clause_id`).
            sparse_embeddings: Optional sparse payloads aligned with `texts`.
            ids: Optional point IDs; defaults to `clause_id`.
        """

        if not texts or not metadatas:
            raise ValueError("texts and metadatas must be provided for insert().")
        dense_vectors = list(embeddings) if embeddings is not None else None
        sparse_vectors_seq = (
            list(sparse_embeddings) if sparse_embeddings is not None else None
        )

        if dense_vectors is None or sparse_vectors_seq is None:
            logger.info("Generating missing embeddings via HybridEmbedder.")
            hybrid_batch = await asyncio.to_thread(self._encode_hybrid_batch, texts)
            if dense_vectors is None:
                dense_vectors = [item.dense for item in hybrid_batch]
            if sparse_vectors_seq is None:
                sparse_vectors_seq = [item.sparse for item in hybrid_batch]

        if dense_vectors is None or sparse_vectors_seq is None:
            raise RuntimeError("Failed to generate hybrid embeddings.")

        if len(dense_vectors) != len(metadatas):
            raise ValueError("Dense embeddings length must match metadatas length.")
        if len(sparse_vectors_seq) != len(metadatas):
            raise ValueError("Sparse embeddings length must match metadatas length.")

        if ids is None:
            ids = [meta.get("clause_id") for meta in metadatas]

        points: List[rest.PointStruct] = []
        for idx, dense in enumerate(dense_vectors):
            if ids[idx] is None:
                raise ValueError("All metadatas or ids must include clause_id.")
            vector_payload: Dict[str, Any] = {"dense": list(map(float, dense))}
            sparse_payload = _convert_sparse_input(sparse_vectors_seq[idx])
            if sparse_payload is not None:
                vector_payload["sparse"] = sparse_payload

            points.append(
                rest.PointStruct(
                    id=str(ids[idx]),
                    vector=vector_payload,
                    payload=metadatas[idx],
                )
            )

        await asyncio.to_thread(
            self.client.upsert,
            collection_name=self.config.collection_name,
            points=points,
            wait=True,
        )

    async def query(
        self,
        *,
        query_dense: Sequence[float] | None = None,
        query_sparse: (
            Dict[int, float] | SparseVectorPayload | Sequence[float] | None
        ) = None,
        query_text: str | None = None,
        alpha: float = 0.7,
        n_results: int = 10,
        where: Dict[str, Any] | None = None,
    ) -> List[VectorMatch]:
        """Query Qdrant with dense+sparse embeddings.

        Args:
            query_dense: Dense embedding list.
            query_sparse: Sparse embedding payload.
            query_text: Raw text; auto-encodes dense+sparse when provided.
            alpha: Dense weight for score fusion.
            n_results: Number of matches to return.
            where: Qdrant payload filter.

        Returns:
            List[VectorMatch]: Sorted by fused score.
        """

        if query_dense is None and query_text:
            embedding = await asyncio.to_thread(HybridEmbedder.encode, query_text)
            query_dense = embedding.dense
            query_sparse = query_sparse or embedding.sparse

        if query_dense is None and query_sparse is None:
            raise ValueError(
                "At least one of query_dense/query_sparse/query_text is required."
            )

        qdrant_filter = _build_filter(where)

        dense_points = await self._search_dense(query_dense, qdrant_filter, n_results)
        sparse_points = await self._search_sparse(
            query_sparse, qdrant_filter, n_results
        )

        matches = _merge_scores(
            dense_points=dense_points,
            sparse_points=sparse_points,
            alpha=alpha,
            limit=n_results,
        )
        return matches

    async def _search_dense(
        self,
        query_dense: Sequence[float] | None,
        qdrant_filter: rest.Filter | None,
        limit: int,
    ) -> List[rest.ScoredPoint]:
        if query_dense is None:
            return []
        named = rest.NamedVector(name="dense", vector=list(map(float, query_dense)))
        return await asyncio.to_thread(
            self.client.search,
            self.config.collection_name,
            query_vector=named,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )

    async def _search_sparse(
        self,
        query_sparse: Dict[int, float] | SparseVectorPayload | Sequence[float] | None,
        qdrant_filter: rest.Filter | None,
        limit: int,
    ) -> List[rest.ScoredPoint]:
        sparse_payload = _convert_sparse_input(query_sparse)
        if sparse_payload is None:
            return []
        named = rest.NamedSparseVector(name="sparse", vector=sparse_payload)
        return await asyncio.to_thread(
            self.client.search,
            self.config.collection_name,
            query_vector=named,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )

    def _encode_hybrid_batch(self, texts: Sequence[str]) -> List[HybridEmbedding]:
        return [HybridEmbedder.encode(text) for text in texts]


def _convert_sparse_input(
    data: (
        Dict[int, float] | SparseVectorPayload | Sequence[float] | Dict[str, Any] | None
    ),
) -> rest.SparseVector | None:
    """Normalise sparse inputs into Qdrant `SparseVector`.

    Args:
        data: Sparse structure (payload dict, `SparseVectorPayload`, list, or None).

    Returns:
        rest.SparseVector | None: Payload ready for Qdrant upsert/search.
    """
    if data is None:
        return None
    if isinstance(data, SparseVectorPayload):
        payload = data.sort()
        return rest.SparseVector(indices=payload.indices, values=payload.values)
    if isinstance(data, dict) and "indices" in data and "values" in data:
        payload = SparseVectorPayload(
            indices=[int(i) for i in data["indices"]],
            values=[float(v) for v in data["values"]],
        ).sort()
        return rest.SparseVector(indices=payload.indices, values=payload.values)
    if isinstance(data, dict):
        indices: List[int] = []
        values: List[float] = []
        for key, value in data.items():
            try:
                idx = int(key)
            except ValueError:
                idx = int(
                    hashlib.blake2b(key.encode("utf-8"), digest_size=8).hexdigest(), 16
                )
            indices.append(idx % SPARSE_HASH_SPACE)
            values.append(float(value))
        payload = SparseVectorPayload(indices=indices, values=values).sort()
        return rest.SparseVector(indices=payload.indices, values=payload.values)
    if isinstance(data, Sequence):
        # interpreted as dense histogram -> convert to sequential indices
        indices = list(range(len(data)))
        values = [float(v) for v in data]
        payload = SparseVectorPayload(indices=indices, values=values).sort()
        return rest.SparseVector(indices=payload.indices, values=payload.values)
    return None


def _build_filter(where: Dict[str, Any] | None) -> rest.Filter | None:
    """Convert simple dict filters into Qdrant FieldConditions."""
    if not where:
        return None
    must: List[rest.FieldCondition] = []
    for key, value in where.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            must.append(
                rest.FieldCondition(key=key, match=rest.MatchAny(any=list(value)))
            )
        else:
            must.append(
                rest.FieldCondition(key=key, match=rest.MatchValue(value=value))
            )
    if not must:
        return None
    return rest.Filter(must=must)


def _merge_scores(
    *,
    dense_points: Sequence[rest.ScoredPoint],
    sparse_points: Sequence[rest.ScoredPoint],
    alpha: float,
    limit: int,
) -> List[VectorMatch]:
    """Fuse dense/sparse search results into ranked matches.

    Args:
        dense_points: Qdrant dense search results.
        sparse_points: Qdrant sparse search results.
        alpha: Dense contribution (0-1).
        limit: Max number of matches to return.

    Returns:
        List[VectorMatch]: Sorted by fused score desc.
    """
    dense_raw, dense_scaled, dense_payload = _extract_scores(dense_points)
    sparse_raw, sparse_scaled, sparse_payload = _extract_scores(sparse_points)

    candidate_ids = set(dense_raw.keys()) | set(sparse_raw.keys())
    matches: List[VectorMatch] = []
    for candidate_id in candidate_ids:
        dense_component = dense_scaled.get(candidate_id)
        sparse_component = sparse_scaled.get(candidate_id)

        if dense_component is None and sparse_component is None:
            continue
        if dense_component is None:
            final_score = sparse_component
        elif sparse_component is None:
            final_score = dense_component
        else:
            final_score = alpha * dense_component + (1 - alpha) * sparse_component

        payload = (
            dense_payload.get(candidate_id) or sparse_payload.get(candidate_id) or {}
        )
        matches.append(
            VectorMatch(
                id=candidate_id,
                payload=payload,
                score=float(final_score),
                dense_score=dense_raw.get(candidate_id),
                sparse_score=sparse_raw.get(candidate_id),
            )
        )

    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[:limit]


def _extract_scores(points: Sequence[rest.ScoredPoint]):
    """Extract raw/normalized scores and payloads from Qdrant results."""
    raw_scores: Dict[str, float] = {}
    scaled_scores: Dict[str, float] = {}
    payloads: Dict[str, Dict[str, Any]] = {}
    if not points:
        return raw_scores, scaled_scores, payloads

    scores = [float(p.score or 0.0) for p in points]
    score_min = min(scores)
    score_max = max(scores)
    denom = score_max - score_min if score_max != score_min else 1.0

    for point in points:
        point_id = str(point.id)
        raw = float(point.score or 0.0)
        raw_scores[point_id] = raw
        scaled_scores[point_id] = (raw - score_min) / denom if denom else 1.0
        payloads[point_id] = dict(point.payload or {})
    return raw_scores, scaled_scores, payloads
