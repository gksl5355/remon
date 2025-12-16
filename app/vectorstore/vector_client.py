#app/vectorstore/vector_client.py
"""
module: vector_client.py
description: Qdrant VectorDB 클라이언트 (삽입 전용 - 검색은 HybridRetriever 사용)
author: AI Agent
created: 2025-11-12
updated: 2025-01-21
dependencies:
    - qdrant-client>=1.15.1
    - app.config.settings
"""

import logging
from typing import List, Dict, Any, Optional
import urllib3
from qdrant_client import QdrantClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from qdrant_client.models import PointStruct, SparseVector
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
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
except ImportError:
    logger.warning("settings.py 로드 실패, 환경변수 사용")
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "remon_regulations")
    QDRANT_PATH = os.getenv("QDRANT_PATH", "./data/qdrant")
    QDRANT_USE_LOCAL = os.getenv("QDRANT_USE_LOCAL", "false").lower() == "true"
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


class VectorClient:
    """
    Qdrant VectorDB 클라이언트 (삽입 전용).

    특징:
    - Dense vector (BGE-M3 1024차원) + Sparse vector (BM25 스타일) 동시 저장
    - 로컬/원격 모드 지원
    - 검색 기능은 HybridRetriever 사용
    """

    def __init__(
        self, collection_name: str = None, use_local: bool = None
    ):
        """
        Qdrant 클라이언트 초기화.

        Args:
            collection_name: 컬렉션 이름 (None이면 환경변수 사용)
            use_local: True면 로컬 저장소, False면 원격 서버, None이면 환경변수 사용
        """
        self.collection_name = collection_name or QDRANT_COLLECTION

        if use_local is None:
            use_local = QDRANT_USE_LOCAL

        if use_local:
            self.client = QdrantClient(path=QDRANT_PATH)
            self._use_requests = False
            logger.info(f"✅ Qdrant 로컬 모드: {QDRANT_PATH}")
        else:
            # 원격 연결: QdrantClient + requests 병행 사용
            qdrant_url = os.getenv("QDRANT_URL", f"https://{QDRANT_HOST}")
            
            # QdrantClient (검색용) - 타임아웃 60초로 증가
            self.client = QdrantClient(
                url=qdrant_url,
                api_key=QDRANT_API_KEY,
                timeout=60,  # 60초 타임아웃
                prefer_grpc=False,
                https=True,
                verify=False  # SSL 검증 우회
            )
            
            # requests (삽입용)
            self._use_requests = True
            self._base_url = qdrant_url
            logger.info(f"✅ Qdrant 원격 모드 (SSL verify=False): {qdrant_url}")
        
        # 컬렉션 존재 확인
        logger.info(f"✅ 컬렉션 사용: {self.collection_name}")

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
        import random

        total = len(texts)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            points = []

            for idx in range(batch_start, batch_end):
                text = texts[idx]
                dense = dense_embeddings[idx]
                meta = metadatas[idx]

                # Qdrant는 정수 ID만 허용 (UUID 문자열 불가)
                point_id = random.randint(1, 2**63 - 1)
                # NumPy float32 → Python float 변환
                dense_list = [float(x) for x in dense]
                vectors = {"dense": dense_list}

                if sparse_embeddings and idx < len(sparse_embeddings):
                    sparse = sparse_embeddings[idx]
                    vectors["sparse"] = {
                        "indices": [int(k) for k in sparse.keys()],
                        "values": [float(v) for v in sparse.values()]
                    }

                payload = {"text": text, **meta}

                points.append({
                    "id": point_id,
                    "vector": vectors,
                    "payload": payload,
                })

            # 원격 모드면 requests 사용 (test_qdrant.py 방식)
            if hasattr(self, '_use_requests'):
                import requests
                url = f"{self._base_url}/collections/{self.collection_name}/points?wait=true"
                headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
                resp = requests.put(
                    url,
                    json={"points": points},
                    headers=headers,
                    verify=False,
                    timeout=30
                )
                resp.raise_for_status()
            elif self.client:
                # 로컬 모드는 QdrantClient 사용
                points_struct = [
                    PointStruct(
                        id=p["id"],
                        vector={k: SparseVector(**v) if k == "sparse" and isinstance(v, dict) else v for k, v in p["vector"].items()},
                        payload=p["payload"]
                    )
                    for p in points
                ]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points_struct,
                    wait=True
                )
            else:
                raise RuntimeError("Qdrant 클라이언트가 초기화되지 않았습니다")
            
            logger.info(
                f"  ✅ 배치 {batch_start//batch_size + 1}/{(total + batch_size - 1)//batch_size}: {len(points)}개 삽입"
            )

        logger.info(f"✅ 총 {total}개 문서 삽입 완료")

    def delete_collection(self) -> None:
        """컬렉션 삭제."""
        if not self.client:
            raise RuntimeError("Qdrant 클라이언트가 초기화되지 않았습니다")
        self.client.delete_collection(collection_name=self.collection_name)
        logger.info(f"✅ 컬렉션 삭제: {self.collection_name}")

    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회."""
        if not self.client:
            raise RuntimeError("Qdrant 클라이언트가 초기화되지 않았습니다")
        info = self.client.get_collection(collection_name=self.collection_name)
        return {
            "name": self.collection_name,
            "points_count": info.points_count,
            "vectors_config": str(info.config.params.vectors),
        }

    def verify_storage(self, sample_size: int = 3) -> Dict[str, Any]:
        """저장 검증: Dense + Sparse + Metadata 확인."""
        if not self.client:
            return {"status": "error", "error": "Qdrant 클라이언트가 초기화되지 않음"}
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_payload=True,
                with_vectors=True,
            )

            points = scroll_result[0]
            verification = {
                "status": "success",
                "collection_name": self.collection_name,
                "total_points": info.points_count,
                "samples": [],
            }

            for point in points:
                sample = {
                    "id": point.id,
                    "has_dense": "dense" in point.vector,
                    "has_sparse": "sparse" in point.vector,
                    "dense_dim": (
                        len(point.vector.get("dense", []))
                        if "dense" in point.vector
                        else 0
                    ),
                    "sparse_dim": (
                        len(point.vector.get("sparse", {}).get("indices", []))
                        if "sparse" in point.vector
                        else 0
                    ),
                    "metadata_keys": list(point.payload.keys()),
                    "text_preview": point.payload.get("text", "")[:100],
                }
                verification["samples"].append(sample)

            return verification
        except Exception as e:
            return {"status": "error", "error": str(e)}
