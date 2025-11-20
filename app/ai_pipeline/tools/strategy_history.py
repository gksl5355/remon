#======================================================================
# app/ai_pipeline/tools/strategy_history.py
# 규제-제품-전략 히스토리 저장용 Qdrant Tool
#
# 저장 스키마(예상 payload):
#   payload = {
#       "meta_collection": <str>,                   # 이 히스토리 컬렉션 이름
#       "meta_regulation_summary": <str>,           # 규제 요약 텍스트
#       "meta_products": [<str>, ...],              # 매핑된 제품명 리스트
#       "meta_product_count": <int>,                # 제품 개수
#       "meta_strategies": [<str>, ...],            # 새로 생성된 대응 전략 리스트
#       "meta_has_strategy": <bool>,                # 전략 존재 여부 플래그
#       "meta_chunk_type": "regulation_product_strategy",
#       "meta_embedding_model": "bge-m3",
#   }
#
# 벡터:
#   - named vector "dense": 규제요약 + 제품을 합친 텍스트 임베딩
#   - named vector "sparse": 동일 텍스트의 SparseVector
#
# 주의:
#   - 이 파일은 "쓰기(저장)"만 담당. 검색은 HybridRetriever 가 담당.
#======================================================================

from __future__ import annotations

from typing import List, Dict, Any
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Distance,
    VectorParams,
    SparseVectorParams,
)

from .hybrid_embedder import HybridEmbedder


class StrategyHistoryTool:
    """
    규제-제품-전략 히스토리를 Qdrant에 저장하는 유틸리티.
    - generate_strategy_node 에서 생성된 전략 리스트를
      한 포인트로 upsert 한다.
    """

    def __init__(
        self,
        collection: str,
        host: str = None,
        port: int | None = None,
    ):
        """
        Parameters
        ----------
        collection : str
            Qdrant collection name (전략 히스토리용 컬렉션)
        host : str, optional
            Qdrant 호스트 (기본값: QDRANT_HOST env 또는 'localhost')
        port : int, optional
            Qdrant 포트 (기본값: QDRANT_PORT env 또는 6333)
        """
        self.collection = collection

        host = host or os.getenv("QDRANT_HOST", "localhost")
        port = port or int(os.getenv("QDRANT_PORT", "6333"))

        # HTTP 클라이언트 사용
        self.client = QdrantClient(url=f"http://{host}:{port}")

        # 규제+제품 텍스트 → dense/sparse 임베딩용
        self.embedder = HybridEmbedder()

    # ------------------------------------------------------------------
    # 컬렉션 존재 보장
    # ------------------------------------------------------------------
    def ensure_collection(self) -> None:
        """
        전략 히스토리 컬렉션이 없을 경우 생성한다.
        - named vectors: dense (cosine), sparse
        """
        try:
            self.client.get_collection(self.collection)
            return
        except Exception as exc:
            msg = str(exc).lower()
            if "not found" not in msg and "doesn't exist" not in msg:
                raise

        # 컬렉션 생성: dense 차원은 임베딩 결과 길이로 결정
        probe = self.embedder.embed("init strategy history")
        dense_dim = len(probe["dense"])

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": VectorParams(
                    size=dense_dim,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )

    # ------------------------------------------------------------------
    # 임베딩용 텍스트 빌드
    # ------------------------------------------------------------------
    def _build_embedding_text(
        self,
        regulation_summary: str,
        mapped_products: List[str],
    ) -> str:
        """
        규제 요약 + 매핑된 제품 리스트를 합쳐서
        임베딩에 사용할 기준 텍스트를 생성한다.
        """
        products_block = (
            ", ".join(mapped_products)
            if mapped_products
            else "(no mapped products)"
        )

        # Retrieval 에서도 규제+제품 조합으로 검색하므로,
        # 여기서도 동일한 패턴으로 텍스트를 구성해 둔다.
        return f"Regulation: {regulation_summary.strip()}\nProducts: {products_block}"

    # ------------------------------------------------------------------
    # 메인: 히스토리 저장
    # ------------------------------------------------------------------
    def save_strategy_history(
        self,
        regulation_summary: str,
        mapped_products: List[str],
        strategies: List[str],
    ) -> None:
        """
        규제 요약 + 매핑된 제품 + 새로 생성된 전략 리스트를
        하나의 포인트로 Qdrant 컬렉션에 저장한다.

        Parameters
        ----------
        regulation_summary : str
            현재 규제 요약 텍스트
        mapped_products : List[str]
            규제와 매핑된 제품명 리스트
        strategies : List[str]
            generate_strategy_node 에서 생성된 대응 전략 문자열 리스트
        """
        # 전략이 아예 없으면 굳이 저장하지 않고 return
        if not strategies:
            return

        # 컬렉션이 없으면 만들고 진행
        self.ensure_collection()

        # 1) 임베딩 텍스트 생성
        embed_text = self._build_embedding_text(
            regulation_summary=regulation_summary,
            mapped_products=mapped_products,
        )

        # 2) Dense + Sparse 임베딩 생성
        emb = self.embedder.embed(embed_text)
        dense_vec = emb["dense"]   # List[float]
        sparse_vec = emb["sparse"] # SparseVector

        # 3) payload 구성
        payload: Dict[str, Any] = {
            "meta_collection": self.collection,
            "meta_regulation_summary": regulation_summary,
            "meta_products": mapped_products,
            "meta_product_count": len(mapped_products),
            "meta_strategies": strategies,
            "meta_has_strategy": bool(strategies),
            "meta_chunk_type": "regulation_product_strategy",
            "meta_embedding_model": "bge-m3",
        }

        # 4) Qdrant PointStruct 생성
        point = PointStruct(
            id=str(uuid.uuid4()),
            payload=payload,
            vector={
                "dense": dense_vec,
                "sparse": sparse_vec,
            },
        )

        # 5) upsert 수행
        #    - 컬렉션 스키마(이름이 "dense", "sparse" 인 named vector)는
        #      미리 생성되어 있다고 가정한다.
        self.client.upsert(
            collection_name=self.collection,
            points=[point],
        )
