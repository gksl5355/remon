#======================================================================
# test_generate_strategy.py
# generate_strategy_node 단일 노드 LLM 호출 테스트
#======================================================================

import os
from types import SimpleNamespace

# (선택) .env에서 환경 변수 로드하고 싶으면:
# pip install python-dotenv 했다면 아래 주석 해제
# from dotenv import load_dotenv
# load_dotenv()

# 프로젝트 루트에서 실행한다고 가정: `python test_generate_strategy.py`
from app.ai_pipeline.nodes.generate_strategy import generate_strategy_node

# --------------------------------------------------------------------
# 1) 더미 규제 텍스트 / 제품 / RAG 컨텍스트 정의
# --------------------------------------------------------------------

DUMMY_REGULATION = """
지금 니코틴 함량이 1 mL당 20 mg을 초과하는 전자담배 액상은
2026년 1월 1일 이후 신규 제조 및 수입이 금지된다.
기존 재고는 2026년 6월 30일까지 소진하여야 하며,
제품 포장 전면의 30% 이상에 경고 문구를 표시해야 한다.
"""

DUMMY_MAPPED_PRODUCTS = [
    "니코틴 30 mg/mL 전자담배 액상 - 제품 A",
    "니코틴 25 mg/mL 전자담배 액상 - 제품 B",
]

DUMMY_RAG_CONTEXT_DOCS = [
    "2023년 유럽연합 액상 니코틴 규제에서는 니코틴 함량 상한선을 20 mg/mL로 제한하고,"
    " 기존 재고에 대해 6개월의 소진 기간을 부여하였다. 당시 대응전략으로는 니코틴 함량 조정,"
    " 재고 소진 프로모션, 포장 경고 문구 확대 등이 사용되었다.",
    "국내 담배 경고문 확대 규제(포장 전면의 30% 이상)에 대해서는,"
    " 패키지 디자인 전면 수정, 인쇄 사양 변경, 온라인몰/오프라인 채널의 소비자 안내 강화가 주요 전략이었다.",
]

# --------------------------------------------------------------------
# 2) 더미 State 생성
#   - 실제 AppState 타입이 뭐든 간에, generate_strategy_node는
#     getattr/setattr만 쓰기 때문에 SimpleNamespace로도 충분히 동작함.
# --------------------------------------------------------------------

def build_dummy_state():
    state = SimpleNamespace(
        regulation_text=DUMMY_REGULATION,
        mapped_products=DUMMY_MAPPED_PRODUCTS,
        rag_context_docs=DUMMY_RAG_CONTEXT_DOCS,
        strategies=[],   # 결과가 여기로 들어갈 예정
    )
    return state


# --------------------------------------------------------------------
# 3) 실행 & 출력
# --------------------------------------------------------------------

def main():
    # OPENAI_API_KEY 확인용 (디버깅)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[WARN] OPENAI_API_KEY가 설정되어 있지 않습니다.")
    else:
        print("[INFO] OPENAI_API_KEY 감지됨 (앞 5글자):", api_key[:5], "****")

    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    temp = os.getenv("TEMPERATURE", "0.0")
    print(f"[INFO] MODEL={model}, TEMPERATURE={temp}")

    # 더미 state 생성
    state = build_dummy_state()

    # 노드 실행
    print("\n=== generate_strategy_node 호출 ===")
    result = generate_strategy_node(state)

    # 결과 출력
    print("\n=== state.strategies ===")
    for i, s in enumerate(state.strategies, start=1):
        print(f"{i}. {s}")

    print("\n=== 함수 반환값(result) ===")
    print(result)


if __name__ == "__main__":
    main()
