#!/usr/bin/env python
"""
Qdrant 검색 직접 테스트
updated: 2025-01-19
"""

import os
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline


def test_search():
    print("=" * 60)
    print("🧪 Qdrant 검색 직접 테스트")
    print("=" * 60)
    
    # 1. 임베딩 생성
    print("\n1️⃣ 임베딩 생성 중...")
    start = time.time()
    embedder = EmbeddingPipeline(use_sparse=True)
    embeddings = embedder.embed_single_text("tobacco")
    print(f"✅ 임베딩 완료 ({time.time() - start:.2f}초)")
    print(f"   Dense 차원: {len(embeddings['dense'])}")
    print(f"   Sparse 키워드: {len(embeddings.get('sparse', {}))}개")
    
    # 2. REST API로 직접 검색 (Dense만)
    print("\n2️⃣ Dense 검색 (REST API)...")
    start = time.time()
    
    url = "https://qdrant.skala25a.project.skala-ai.com/collections/skala-2.4.17-regulation/points/query"
    headers = {
        "api-key": os.getenv("QDRANT_API_KEY"),
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": embeddings["dense"],
        "using": "dense",
        "limit": 3,
        "with_payload": True
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            verify=False,
            timeout=30
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            results = response.json()["result"]["points"]
            print(f"✅ 검색 완료 ({elapsed:.2f}초)")
            print(f"   결과: {len(results)}개")
            
            for i, r in enumerate(results, 1):
                print(f"\n   [{i}] ID: {r['id']}, Score: {r['score']:.3f}")
                print(f"       제목: {r['payload'].get('title', 'N/A')[:50]}")
        else:
            print(f"❌ 검색 실패: {response.status_code}")
            print(f"   응답: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"❌ 타임아웃 ({time.time() - start:.2f}초)")
    except Exception as e:
        print(f"❌ 오류: {e}")
    
    # 3. QdrantClient로 검색
    print("\n3️⃣ QdrantClient로 검색...")
    start = time.time()
    
    try:
        from qdrant_client import QdrantClient
        
        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=30,
            prefer_grpc=False,
            https=True,
            verify=False
        )
        
        results = list(client.query_points(
            collection_name="skala-2.4.17-regulation",
            query=embeddings["dense"],
            using="dense",
            limit=3,
            with_payload=True
        ))
        
        elapsed = time.time() - start
        print(f"✅ 검색 완료 ({elapsed:.2f}초)")
        print(f"   결과: {len(results)}개")
        
        for i, r in enumerate(results, 1):
            print(f"\n   [{i}] ID: {r.id}, Score: {r.score:.3f}")
            print(f"       제목: {r.payload.get('title', 'N/A')[:50]}")
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        print(f"   경과 시간: {time.time() - start:.2f}초")


if __name__ == "__main__":
    test_search()
