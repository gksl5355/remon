"""
로컬 Qdrant(예: http://127.0.0.1:6333)에 포인트 1건을 업서트하는 스크립트.
벡터는 더미 임베딩(해시 기반)으로 생성하고, payload는 주신 예시를 포함한다.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# 기본 설정 (필요 시 환경변수로 덮어쓰기)
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "remon_regulations")
QDRANT_VECTOR_NAME = os.getenv("QDRANT_VECTOR_NAME", "dense")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)


def make_dummy_embedding(text: str, dim: int = 1024) -> List[float]:
    """외부 모델 없이 해시 기반으로 1024차 벡터 생성."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [(b / 255.0) for b in h]
    return (vals * (dim // len(vals) + 1))[:dim]


def build_point(point_id: int, regulation_meta: Dict[str, Any]) -> PointStruct:
    snippet = regulation_meta["new_snippet"]
    dense_vec = make_dummy_embedding(snippet, dim=1024)

    payload: Dict[str, Any] = {
        "text": snippet,
        "ref_id": regulation_meta.get("ref_id", "demo_ref"),
        "regulation_id": regulation_meta.get("regulation_id", "demo_regulation"),
        "content_type": "text",
        "page_num": 1,
        "hierarchy": ["Section", "Clause"],
        "token_count": len(snippet.split()),
        "jurisdiction_code": regulation_meta.get("country"),
        "authority": regulation_meta.get("authority"),
        "title": regulation_meta.get("title"),
        "citation_code": regulation_meta.get("citation_code"),
        "language": regulation_meta.get("language", "en"),
        "effective_date": regulation_meta.get("effective_date"),
        "section_label": regulation_meta.get("section_label", "Section 1"),
        "keywords": regulation_meta.get("keywords", []),
        "country": regulation_meta.get("country"),
        "regulation_type": regulation_meta.get("regulation_type", "FDA"),
        "meta_source": regulation_meta.get("meta_source", "local_test"),
    }

    return PointStruct(
        id=point_id,
        vector={QDRANT_VECTOR_NAME: dense_vec},
        payload=payload,
    )


def main():
    # 필요 시 환경변수 POINT_ID로 지정, 없으면 기본값 사용
    point_id = int(os.getenv("POINT_ID", "35186518330133973"))
    # state.regulation에 맞춘 메타데이터 예시
    # KST 기준 ISO 날짜/시간
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(tz=kst)
    now_iso = now_kst.isoformat()
    regulation_meta = {
        "new_snippet": "니코틴 함량은 12mg을 초과할 수 없다...",  # 더 낮은 요구치
        "ref_id": "FDA-US-Required-Warnings-Cigarette-Chunk0001",
        "regulation_id": "FDA-US-Required-Warnings-Cigarette",
        "title": "Required Warnings for Cigarette Packages and Advertising",
        "citation_code": "21 CFR 1141",
        "country": "US",
        "authority": "Food and Drug Administration",
        "effective_date": now_iso[:10],  # KST 기준 오늘 날짜
        "keywords": ["nicotine", "limit", "warning"],
        "regulation_type": "FDA",
        "meta_source": "local_test",
        "section_label": "Nicotine Limit",
        "language": "ko",
    }

    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        prefer_grpc=False,
        timeout=30.0,
    )

    point = build_point(point_id, regulation_meta)
    res = client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[point],
        wait=True,
    )
    print(f"Upserted point_id={point_id} into {QDRANT_COLLECTION}, status={res.status}")


if __name__ == "__main__":
    main()
