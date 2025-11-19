# app/ai_pipeline/test_hybrid_search.py

from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from qdrant_client import QdrantClient


def main():
    print("🚀 HybridRetriever 안정성 테스트 (확실한 버전)\n")

    # -------------------------------
    # 1) 클라이언트 타입 확인
    # -------------------------------
    client = QdrantClient(url="http://localhost:6333")
    print(f"🔍 QdrantClient 생성 완료: {client}")

    print("\n➡ search() 존재 여부 확인:")
    print("hasattr(client, 'search') =", hasattr(client, "search"))
    print("hasattr(client, 'search_points') =", hasattr(client, "search_points"))

    # search가 없어도 search_points가 있으면 신버전
    if not hasattr(client, "search"):
        print("\n❌ 현재 QdrantClient 에 search() 없음 → 구버전 retriever는 동작 불가")
        print("   해결: fusion_hybrid_retriever 내부에서 QdrantClient(host,port) → url 방식으로 변경 필요")
    else:
        print("\n✔ search() 존재 확인됨 → 구버전 API 사용 가능")

    print("\n---------------------------------------")
    print("🧪 2) 실제 HybridRetriever 검색 실행")
    print("---------------------------------------\n")

    # -------------------------------
    # 2) HybridRetriever 실행
    # -------------------------------
    retriever = HybridRetriever(
        default_collection="remon_regulations",       # 반드시 너의 collection명
        host="localhost",
        port=6333
    )

    query = "nicotine regulation label"

    try:
        results = retriever.search(query=query, limit=5)

        print("====== 검색 결과 ======\n")
        if not results:
            print("⚠ 검색 결과가 없습니다 (collection 또는 데이터 확인 필요)")
        else:
            for r in results:
                print(f"- ID: {r['id']}")
                print(f"  Score: {r['score']:.4f}")
                print(f"  Payload: {r['payload']}\n")

    except Exception as e:
        print(f"\n❌ 검색 중 오류 발생: {e}")

    print("\n🎉 테스트 종료!")


if __name__ == "__main__":
    main()
