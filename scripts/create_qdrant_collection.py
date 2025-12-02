#!/usr/bin/env python
"""
클라우드 Qdrant에 컬렉션 생성 스크립트

Usage:
    uv run python scripts/create_qdrant_collection.py
    uv run python scripts/create_qdrant_collection.py --collection my_collection
    uv run python scripts/create_qdrant_collection.py --reset  # 기존 컬렉션 삭제 후 재생성
"""

import os
import sys
import argparse
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams


def create_collection(collection_name: str, reset: bool = False):
    """클라우드 Qdrant에 컬렉션 생성"""
    
    # 환경변수 로드
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    if not qdrant_url:
        print("❌ QDRANT_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    if not qdrant_api_key:
        print("❌ QDRANT_API_KEY 환경변수가 설정되지 않았습니다.")
        return False
    
    print(f"🔗 연결 중: {qdrant_url}")
    print(f"🔑 API Key: {qdrant_api_key[:10]}...")
    
    try:
        # 클라이언트 생성
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=60,
            prefer_grpc=False
        )
        
        # 기존 컬렉션 확인
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if exists:
            if reset:
                print(f"🗑️  기존 컬렉션 삭제 중: {collection_name}")
                client.delete_collection(collection_name=collection_name)
                print("✅ 삭제 완료")
            else:
                print(f"⚠️  컬렉션이 이미 존재합니다: {collection_name}")
                print("   --reset 옵션으로 재생성하거나 다른 이름을 사용하세요.")
                return False
        
        # 컬렉션 생성
        print(f"📦 컬렉션 생성 중: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=1024,  # BGE-M3
                    distance=Distance.COSINE
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )
        
        print("✅ 컬렉션 생성 완료")
        
        # 컬렉션 정보 확인
        info = client.get_collection(collection_name=collection_name)
        print(f"\n📊 컬렉션 정보:")
        print(f"   이름: {collection_name}")
        print(f"   포인트 수: {info.points_count}")
        print(f"   벡터 설정: {info.config.params.vectors}")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="클라우드 Qdrant 컬렉션 생성")
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="컬렉션 이름 (기본값: .env의 QDRANT_COLLECTION)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="기존 컬렉션 삭제 후 재생성"
    )
    
    args = parser.parse_args()
    
    collection_name = args.collection or os.getenv("QDRANT_COLLECTION", "skala-2.4.17-regulation")
    
    print("=" * 60)
    print("🚀 클라우드 Qdrant 컬렉션 생성")
    print("=" * 60)
    print(f"컬렉션명: {collection_name}")
    print(f"재생성 모드: {'활성화' if args.reset else '비활성화'}")
    print()
    
    success = create_collection(collection_name, args.reset)
    
    if success:
        print("\n✅ 작업 완료")
    else:
        print("\n❌ 작업 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
