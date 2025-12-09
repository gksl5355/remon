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

import requests
import urllib3
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, SparseVectorParams

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_collection(collection_name: str, reset: bool = False, collection_type: str = "regulation"):
    """
    클라우드 Qdrant에 컬렉션 생성
    
    Args:
        collection_name: 컬렉션 이름
        reset: 기존 컬렉션 삭제 후 재생성
        collection_type: "regulation" (규제 문서) 또는 "strategy" (전략 히스토리)
    """
    
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
    print("🔑 API 인증 완료")
    
    try:
        # requests 라이브러리 사용 (vector_client.py 방식)
        print("🔍 서버 연결 테스트 중...")
        headers = {"api-key": qdrant_api_key}
        response = requests.get(
            f"{qdrant_url}/collections",
            headers=headers,
            verify=False,  # SSL 검증 우회
            timeout=30
        )
        response.raise_for_status()
        collections_data = response.json()["result"]["collections"]
        print(f"✅ 연결 성공 (기존 컬렉션: {len(collections_data)}개)")
        
        # 기존 컬렉션 확인
        exists = any(c["name"] == collection_name for c in collections_data)
        
        if exists:
            if reset:
                print(f"🗑️  기존 컬렉션 삭제 중: {collection_name}")
                response = requests.delete(
                    f"{qdrant_url}/collections/{collection_name}",
                    headers=headers,
                    verify=False,
                    timeout=30
                )
                response.raise_for_status()
                print("✅ 삭제 완료")
            else:
                print(f"⚠️  컬렉션이 이미 존재합니다: {collection_name}")
                print("   --reset 옵션으로 재생성하거나 다른 이름을 사용하세요.")
                return False
        
        # 컬렉션 생성
        print(f"📦 컬렉션 생성 중: {collection_name} (타입: {collection_type})")
        
        # 벡터 설정 (모든 타입 동일: dense + sparse)
        create_payload = {
            "vectors": {
                "dense": {
                    "size": 1024,
                    "distance": "Cosine"
                }
            },
            "sparse_vectors": {
                "sparse": {}
            }
        }
        
        response = requests.put(
            f"{qdrant_url}/collections/{collection_name}",
            headers={**headers, "Content-Type": "application/json"},
            json=create_payload,
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        print("✅ 컬렉션 생성 완료")
        
        # 컬렉션 정보 확인
        response = requests.get(
            f"{qdrant_url}/collections/{collection_name}",
            headers=headers,
            verify=False,
            timeout=30
        )
        response.raise_for_status()
        info = response.json()["result"]
        print(f"\n📊 컬렉션 정보:")
        print(f"   이름: {collection_name}")
        print(f"   포인트 수: {info['points_count']}")
        print(f"   벡터 설정: dense(1024) + sparse")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 오류 발생: {e}")
        print(f"\n🔧 트러블슈팅:")
        print(f"   1. Qdrant 서버 확인: {qdrant_url}")
        print(f"   2. API 키 확인: .env의 QDRANT_API_KEY")
        print(f"   3. 네트워크 연결 확인")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
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
        "--type",
        type=str,
        choices=["regulation", "strategy"],
        default="regulation",
        help="컬렉션 타입 (regulation: 규제 문서, strategy: 전략 히스토리)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="기존 컬렉션 삭제 후 재생성"
    )
    
    args = parser.parse_args()
    
    if args.type == "strategy":
        collection_name = args.collection or "skala-2.4.17-strategy"
    else:
        collection_name = args.collection or os.getenv("QDRANT_COLLECTION", "skala-2.4.17-regulation")
    
    print("=" * 60)
    print("🚀 클라우드 Qdrant 컬렉션 생성")
    print("=" * 60)
    print(f"컬렉션명: {collection_name}")
    print(f"타입: {args.type}")
    print(f"재생성 모드: {'활성화' if args.reset else '비활성화'}")
    print()
    
    success = create_collection(collection_name, args.reset, args.type)
    
    if success:
        print("\n✅ 작업 완료")
    else:
        print("\n❌ 작업 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
