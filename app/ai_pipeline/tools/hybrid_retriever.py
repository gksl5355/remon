# app/ai_pipeline/tools/hybrid_retriever.py
# updated: 2025-01-19 - REST API 완전 전환 (SDK 제거)

from typing import Any, Dict, List, Optional
import os
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .hybrid_embedder import HybridEmbedder

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid Retriever (REST API 전용)
    - dense (BGE-M3)
    - sparse (BoW 50k)
    - Qdrant REST API로 하이브리드 검색 (SDK 미사용)
    """

    def __init__(
        self,
        default_collection: str,
        host: str = None,
        port: int = None,
        url: str | None = None,
        api_key: str | None = None,
        prefer_grpc: bool = False,
        timeout: float = 60.0,
        vector_name: str = "dense",
    ):
        # REST API 전용 (vector_client.py 방식)
        self._base_url = url or os.getenv("QDRANT_URL", "https://qdrant.skala25a.project.skala-ai.com")
        self._api_key = api_key or os.getenv("QDRANT_API_KEY")
        self._timeout = timeout
        self.default_collection = default_collection
        self.vector_name = vector_name
        self.embedder = HybridEmbedder()
        logger.info(f"✅ HybridRetriever REST API 모드: {self._base_url}")

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
        하이브리드 검색 (REST API 사용, dense + sparse RRF 결합).
        """
        import requests
        import time
        
        collection_name = collection or self.default_collection
        if not collection_name:
            raise ValueError("Collection name must be provided.")

        # 1) 임베딩 생성
        emb = self.embedder.embed(query)
        dense_vec = emb["dense"]
        sparse_vec = emb.get("sparse")

        # 2) REST API 엔드포인트
        url = f"{self._base_url}/collections/{collection_name}/points/query"
        headers = {"api-key": self._api_key, "Content-Type": "application/json"}

        # 3) 재시도 로직 (3회)
        dense_results = []
        sparse_results = []
        
        for attempt in range(3):
            try:
                # Dense 검색 (NumPy float32 → Python float)
                dense_payload = {
                    "query": [float(x) for x in dense_vec],
                    "using": "dense",
                    "limit": limit * 2,
                    "with_payload": True
                }
                
                response = requests.post(
                    url, json=dense_payload, headers=headers, 
                    verify=False, timeout=self._timeout
                )
                response.raise_for_status()
                dense_results = response.json()["result"]["points"]
                
                # Sparse 검색 (있으면)
                if sparse_vec:
                    sparse_payload = {
                        "query": {
                            "indices": [int(k) for k in sparse_vec.indices],
                            "values": [float(v) for v in sparse_vec.values]
                        },
                        "using": "sparse",
                        "limit": limit * 2,
                        "with_payload": True
                    }
                    
                    try:
                        response = requests.post(
                            url, json=sparse_payload, headers=headers,
                            verify=False, timeout=self._timeout
                        )
                        response.raise_for_status()
                        sparse_results = response.json()["result"]["points"]
                    except Exception:
                        pass  # Sparse 실패는 무시
                
                break  # 성공
                
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"⚠️ 하이브리드 검색 실패 (attempt {attempt+1}/3), {wait}초 후 재시도: {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"❌ 하이브리드 검색 최종 실패: {e}")
                    raise

        # 4) RRF 결합
        scores = {}
        payloads = {}
        dense_scores = {}
        sparse_scores = {}

        for rank, r in enumerate(dense_results, 1):
            rrf_score = dense_weight * (1 / (rank + 60))
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + rrf_score
            dense_scores[doc_id] = r["score"]
            payloads[doc_id] = r["payload"]

        for rank, r in enumerate(sparse_results, 1):
            rrf_score = sparse_weight * (1 / (rank + 60))
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + rrf_score
            sparse_scores[doc_id] = r["score"]
            if doc_id not in payloads:
                payloads[doc_id] = r["payload"]

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:limit]

        fused: List[Dict[str, Any]] = []
        for doc_id in sorted_ids:
            fused.append({
                "id": doc_id,
                "score": scores[doc_id],
                "payload": payloads[doc_id],
                "text": payloads[doc_id].get("text", ""),
                "scores": {
                    "dense_score": dense_scores.get(doc_id, 0.0),
                    "sparse_score": sparse_scores.get(doc_id, 0.0),
                    "final_score": scores[doc_id],
                },
            })

        return fused
    

