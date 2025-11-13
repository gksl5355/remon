#!/usr/bin/env python3
"""Qdrant 서버 연결 테스트"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vectorstore.vector_client import VectorClient
import numpy as np

def test_connection():
    print("🔍 Qdrant 서버 연결 테스트...\n")
    
    try:
        # 1. 연결 테스트
        print("[1/3] 연결 테스트...")
        vc = VectorClient()
        info = vc.get_collection_info()
        print(f"✅ 컬렉션 정보: {info}\n")
        
        # 2. 샘플 데이터 저장
        print("[2/3] 샘플 데이터 저장 중...")
        vc.insert(
            texts=["테스트 문서 1", "테스트 문서 2"],
            dense_embeddings=[
                np.random.rand(1024).tolist(),
                np.random.rand(1024).tolist()
            ],
            metadatas=[
                {"meta_country": "US", "meta_regulation_id": 1},
                {"meta_country": "KR", "meta_regulation_id": 2}
            ]
        )
        print("✅ 저장 완료\n")
        
        # 3. 검색 테스트
        print("[3/3] 검색 테스트...")
        results = vc.search(
            query_dense=np.random.rand(1024).tolist(),
            top_k=2
        )
        print(f"✅ 검색 결과: {len(results['ids'])}개")
        print(f"   문서: {results['documents']}\n")
        
        print("=" * 60)
        print("✅ 모든 테스트 통과!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        print("\n확인 사항:")
        print("  1. Qdrant 서버 실행 여부: docker ps | grep qdrant")
        print("  2. .env 파일 설정: QDRANT_USE_LOCAL=false")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
