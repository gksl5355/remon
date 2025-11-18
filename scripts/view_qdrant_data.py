#!/usr/bin/env python3
"""
Qdrant에 저장된 데이터 조회 스크립트
실행: python scripts/view_qdrant_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vectorstore.vector_client import VectorClient
import json


def view_data(limit=5):
    """Qdrant 데이터 조회"""
    vc = VectorClient()
    
    print("\n" + "="*80)
    print("📊 Qdrant 저장 데이터 조회")
    print("="*80 + "\n")
    
    # 전체 통계
    info = vc.get_collection_info()
    print(f"컬렉션: {vc.collection_name}")
    print(f"총 포인트 수: {info.get('points_count', 'N/A')}\n")
    
    # 데이터 조회
    results = vc.client.scroll(
        collection_name=vc.collection_name,
        limit=limit,
        with_payload=True,
        with_vectors=True
    )
    
    if not results[0]:
        print("❌ 저장된 데이터가 없습니다.\n")
        return
    
    print(f"📋 최근 {len(results[0])}개 포인트:\n")
    
    for idx, point in enumerate(results[0], 1):
        print(f"{'='*80}")
        print(f"[포인트 {idx}]")
        print(f"{'='*80}\n")
        
        # ID
        print(f"🆔 ID: {point.id}\n")
        
        # 벡터 정보
        if 'dense' in point.vector:
            dense = point.vector['dense']
            print(f"📐 Dense Vector:")
            print(f"   차원: {len(dense)}")
            print(f"   샘플 (처음 10개): {dense[:10]}")
        
        if 'sparse' in point.vector:
            sparse = point.vector['sparse']
            print(f"\n🔍 Sparse Vector:")
            print(f"   {sparse}")
        
        print()
        
        # 메타데이터 (전체)
        print(f"📝 메타데이터 (전체 {len(point.payload)}개 필드):")
        payload = point.payload
        
        for key, value in sorted(payload.items()):
            if key == 'text':
                print(f"   {key} (명제): {value}")
            elif key == 'meta_parent_content':
                print(f"   {key} (원본 청크): {value[:200]}...")
            elif isinstance(value, str) and len(value) > 200:
                print(f"   {key}: {value[:200]}...")
            else:
                print(f"   {key}: {value}")
        
        print(f"\n{'='*80}\n")
    
    # JSON 저장 옵션
    save = input("JSON 파일로 저장하시겠습니까? (y/n): ").strip().lower()
    if save == 'y':
        output = []
        for point in results[0]:
            output.append({
                "id": point.id,
                "vector": {
                    "dense_dim": len(point.vector.get('dense', [])),
                    "dense_sample": point.vector.get('dense', [])[:10],
                    "sparse": point.vector.get('sparse', None)
                },
                "payload": point.payload
            })
        
        output_file = Path(__file__).parent.parent / "data" / "qdrant_sample.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 저장 완료: {output_file}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Qdrant 데이터 조회")
    parser.add_argument("--limit", type=int, default=5, help="조회할 포인트 수 (기본: 5)")
    args = parser.parse_args()
    
    view_data(limit=args.limit)
