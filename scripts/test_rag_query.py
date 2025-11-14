#!/usr/bin/env python3
"""
RAG 쿼리 테스트 콘솔
Qdrant에 저장된 데이터로 OpenAI 기반 질의응답 테스트
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vectorstore.vector_client import VectorClient
from app.ai_pipeline.preprocess.embedding_pipeline import EmbeddingPipeline
import os

try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("❌ openai 미설치. pip install openai 필요")
    sys.exit(1)


class SimpleRAG:
    """간단한 RAG 시스템"""

    def __init__(self):
        try:
            self.vc = VectorClient()
            print("✅ Qdrant 벡터DB 연결 완료")
        except Exception as e:
            print(f"⚠️  drant 연결 실패: {e}")
            self.vc = None

        try:
            # 임베딩 모델 로드 시도
            self.embedder = EmbeddingPipeline(use_sparse=False)
            print("✅ 임베딩 모델 로드 완료")
        except Exception as e:
            print(f"❌ 임베딩 모델 로드 실패: {e}")
            print("   해결방법: uv pip install sentence-transformers FlagEmbedding")
            self.embedder = None

        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not os.getenv("OPENAI_API_KEY"):
                print("⚠️  OPENAI_API_KEY 환경변수 미설정")
            else:
                print("✅ OpenAI 클라이언트 초기화 완료")
        except Exception as e:
            print(f"❌ OpenAI 클라이언트 초기화 실패: {e}")
            self.client = None

        print()

    def search(self, query: str, top_k: int = 3):
        """Qdrant 검색"""
        if self.embedder is None:
            print("❌ 오류: 임베딩 모델 미로드")
            return {"ids": [], "documents": [], "metadatas": [], "scores": []}

        if self.vc is None:
            print("❌ 오류: Qdrant 연결 실패")
            return {"ids": [], "documents": [], "metadatas": [], "scores": []}

        print(f"🔍 검색 중: '{query}'")

        try:
            # 쿼리 임베딩
            query_result = self.embedder.embed_single_text(query)
            query_emb = query_result.get("dense")

            if query_emb is None:
                print("❌ 오류: 쿼리 임베딩 생성 실패")
                return {"ids": [], "documents": [], "metadatas": [], "scores": []}

            # Qdrant 검색
            results = self.vc.search(query_dense=query_emb, top_k=top_k)

            print(f"✅ {len(results.get('ids', []))}개 결과 발견\n")
            return results

        except Exception as e:
            print(f"❌ 검색 중 오류: {e}")
            return {"ids": [], "documents": [], "metadatas": [], "scores": []}

    def generate_answer(self, query: str, search_results):
        """OpenAI로 답변 생성"""
        if self.client is None:
            print("❌ 오류: OpenAI 클라이언트 미초기화")
            return "답변을 생성할 수 없습니다."

        if not search_results.get("ids"):
            return "검색 결과가 없어서 답변을 생성할 수 없습니다."

        try:
            # 컨텍스트 구성
            context_parts = []
            for idx, (doc, meta, score) in enumerate(
                zip(
                    search_results.get("documents", []),
                    search_results.get("metadatas", []),
                    search_results.get("scores", []),
                ),
                1,
            ):
                context_parts.append(
                    f"[문서 {idx}] (관련도: {score:.2f})\n"
                    f"출처: {meta.get('meta_title', 'N/A')}\n"
                    f"내용: {doc}\n"
                )

            context = "\n".join(context_parts)

            # OpenAI 호출
            print("🤖 답변 생성 중...\n")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a regulatory documents expert. Answer accurately based on the provided documents, and present numerical or tabular content as well-formatted tables.",
                    },
                    {
                        "role": "user",
                        "content": f"질문: {query}\n\n참고 문서:\n{context}\n\n위 문서를 바탕으로 답변해주세요.",
                    },
                ],
                temperature=0.3,
                max_tokens=500,
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ 답변 생성 중 오류: {e}")
            return f"답변 생성 실패: {e}"

    def query(self, question: str):
        """전체 RAG 파이프라인"""
        print("=" * 70)
        print(f"질문: {question}")
        print("=" * 70 + "\n")

        # 1. 검색
        results = self.search(question, top_k=3)

        if not results.get("ids"):
            print("❌ 관련 문서를 찾을 수 없습니다.\n")
            return

        # 2. 검색 결과 출력
        print("📚 검색된 문서:\n")
        for idx, (doc, meta, score) in enumerate(
            zip(
                results.get("documents", []),
                results.get("metadatas", []),
                results.get("scores", []),
            ),
            1,
        ):
            print(f"[{idx}] {meta.get('meta_title', 'N/A')} (관련도: {score:.2f})")
            print(f"    {doc[:100]}...\n")

        # 3. 답변 생성
        answer = self.generate_answer(question, results)

        print("=" * 70)
        print("💡 답변:")
        print("=" * 70)
        print(answer)
        print("=" * 70 + "\n")


def interactive_mode():
    """대화형 모드"""
    rag = SimpleRAG()

    print("=" * 70)
    print("🎯 REMON RAG 쿼리 테스트 콘솔")
    print("=" * 70)
    print("명령어:")
    print("  - 질문 입력: 자유롭게 질문하세요")
    print("  - 'exit' 또는 'quit': 종료")
    print("=" * 70 + "\n")

    while True:
        try:
            query = input("\n질문> ").strip()

            if not query:
                continue

            if query.lower() in ["exit", "quit", "q"]:
                print("\n👋 종료합니다.")
                break

            rag.query(query)

        except KeyboardInterrupt:
            print("\n\n👋 종료합니다.")
            break
        except Exception as e:
            print(f"\n❌ 오류: {e}\n")


def test_mode():
    """테스트 모드 (샘플 질문)"""
    rag = SimpleRAG()

    test_questions = [
        "담배 규제의 주요 내용은?",
        "FDA의 역할은 무엇인가?",
        "니코틴 함량 제한은?",
    ]

    print("=" * 70)
    print("🧪 테스트 모드: 샘플 질문 3개")
    print("=" * 70 + "\n")

    for question in test_questions:
        rag.query(question)
        input("\n[Enter를 눌러 다음 질문으로...]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG 쿼리 테스트")
    parser.add_argument("--test", action="store_true", help="테스트 모드 (샘플 질문)")
    args = parser.parse_args()

    if args.test:
        test_mode()
    else:
        interactive_mode()
