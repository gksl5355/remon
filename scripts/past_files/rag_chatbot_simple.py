#!/usr/bin/env python
"""
RAG 챗봇 (간소화 버전 - 모델 재사용)
updated: 2025-01-19
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from openai import OpenAI

# 전역 변수로 모델 캐싱
_embedder = None
_vector_client = None


def get_embedder():
    """임베딩 파이프라인 싱글톤"""
    global _embedder
    if _embedder is None:
        print("🔄 임베딩 모델 로딩 중...")
        from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
        _embedder = EmbeddingPipeline(use_sparse=True)
        print("✅ 임베딩 모델 준비 완료")
    return _embedder


def get_vector_client():
    """VectorClient 싱글톤"""
    global _vector_client
    if _vector_client is None:
        from app.vectorstore.vector_client import VectorClient
        _vector_client = VectorClient(
            collection_name="skala-2.4.17-regulation",
            use_local=False
        )
    return _vector_client


def search_regulations(query: str, top_k: int = 3):
    """규제 문서 하이브리드 검색"""
    print(f"\n🔍 검색: '{query}'")
    
    # 임베딩 생성
    embedder = get_embedder()
    print("  ⏳ 임베딩 생성 중...")
    embeddings = embedder.embed_single_text(query)
    print("  ✅ 임베딩 완료")
    
    # 하이브리드 검색
    vector_client = get_vector_client()
    print("  ⏳ Qdrant 검색 중...")
    results = vector_client.search(
        query_dense=embeddings["dense"],
        query_sparse=embeddings.get("sparse"),
        top_k=top_k,
        hybrid_alpha=0.7
    )
    print(f"  ✅ {len(results['documents'])}개 문서 검색 완료\n")
    
    # 결과 출력
    for i, (doc, meta, score) in enumerate(zip(
        results["documents"], 
        results["metadatas"], 
        results["scores"]
    ), 1):
        dense_score = meta.get('_dense_score') or 0.0
        sparse_score = meta.get('_sparse_score') or 0.0
        
        print(f"📄 결과 {i} (RRF: {score:.3f})")
        print(f"   🔢 Dense: {dense_score:.3f} | Sparse: {sparse_score:.3f}")
        print(f"   🌍 국가: {meta.get('country', 'N/A')}")
        print(f"   📋 제목: {meta.get('title', 'N/A')[:60]}...")
        print(f"   📄 페이지: {meta.get('page_num', 'N/A')}")
        print(f"   📝 내용: {doc[:150]}...")
        print()
    
    return results


def generate_answer(query: str, context_docs: list[str]):
    """LLM 답변 생성"""
    print("🤖 답변 생성 중...\n")
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    context = "\n\n".join([f"[문서 {i+1}]\n{doc}" for i, doc in enumerate(context_docs)])
    
    prompt = f"""다음 규제 문서를 참고하여 질문에 답변하세요.

규제 문서:
{context}

질문: {query}

답변 (한국어로, 간결하게):"""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 규제 전문가입니다. 제공된 문서를 기반으로 정확하게 답변하세요."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=500
    )
    
    answer = response.choices[0].message.content
    print(f"💬 답변:\n{answer}\n")
    
    return answer


def main():
    print("=" * 60)
    print("🤖 RAG 챗봇 (간소화 버전)")
    print("=" * 60)
    print("명령어: 'quit' 또는 'exit' - 종료")
    print("=" * 60)
    
    # 모델 사전 로드
    get_embedder()
    get_vector_client()
    
    print("\n✅ 준비 완료! 질문을 입력하세요.\n")
    
    while True:
        try:
            query = input("💬 질문: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ["quit", "exit", "종료"]:
                print("\n👋 챗봇을 종료합니다.")
                break
            
            # 검색 + 답변
            results = search_regulations(query, top_k=3)
            generate_answer(query, results["documents"])
            
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\n\n👋 챗봇을 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류: {e}\n")


if __name__ == "__main__":
    main()
