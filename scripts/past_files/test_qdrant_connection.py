#!/usr/bin/env python
"""
Qdrant 연결 테스트 스크립트
updated: 2025-01-19
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from qdrant_client import QdrantClient

def test_connection():
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    print("=" * 60)
    print("🧪 Qdrant 연결 테스트")
    print("=" * 60)
    print(f"URL: {qdrant_url}")
    print("API 인증: 설정됨" if qdrant_api_key else "API 인증: 미설정")
    print()
    
    try:
        print("⏳ 연결 시도 중...")
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30,
            prefer_grpc=False
        )
        
        print("📋 컬렉션 목록 조회 중...")
        collections = client.get_collections().collections
        
        print(f"\n✅ 연결 성공!")
        print(f"\n📊 기존 컬렉션: {len(collections)}개")
        for col in collections:
            print(f"   - {col.name}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 연결 실패: {e}")
        print(f"\n🔧 확인 사항:")
        print(f"   1. Qdrant 서버 상태")
        print(f"   2. .env 파일의 QDRANT_URL, QDRANT_API_KEY")
        print(f"   3. 네트워크 연결 (방화벽/VPN)")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
