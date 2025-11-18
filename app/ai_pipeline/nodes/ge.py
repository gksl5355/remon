#======================================================================
# app/ai_pipeline/nodes/generate_strategy.py
# 규제 대응 전략 생성 노드 (MVP)
#
# [State 입출력 요약]
# --- INPUT (from AppState) ---
#   regulation_text: str                    # 규제 원문 텍스트
#   regulation_effective_date: str          # 규제 시행일 (예: "2026-01-01")
#   mapped_products: List[str]              # 매핑된 제품명 리스트
#   regulation_product_embedding: List[float]  # 규제-제품 매핑 결과 임베딩
#
# --- OUTPUT (to AppState) ---
#   strategies: List[str]                   # 최종 규제 대응 전략 리스트
#
# [큰 흐름]
#   1) map_products 노드에서 생성된 규제-제품 임베딩
#      (state.regulation_product_embedding)을 입력으로 받는다.
#   2) retrieval_tools (예: search_history_for_strategy)를 호출하여
#      - VectorDB(Qdrant)에 저장된 과거 (규제-제품-대응전략) history 중
#      - 현재 규제-제품 임베딩과 유사한 포인트를 검색한다.
#      - 과거 대응 전략은 payload 메타데이터에서 text로 가져온다.
#   3) 가져온 히스토리(과거 대응 전략)를 참고하여
#      - 현재 규제(state.regulation_text)에 대한 대응 전략을
#        LLM에게 생성·보완하도록 프롬프트를 구성한다.
#   4) LLM 결과에서 라인별 전략을 파싱하고,
#      자카드 유사도로 너무 비슷한 문장만 후처리로 제거한다.
#   5) {"strategies": List[str]} 형태로 반환하여 AppState에 merge.
#
#   ※ 이 노드(MVP)에서는 history를 새로 DB/Qdrant에 저장하지 않는다.
#======================================================================

from __future__ import annotations

from typing import List, Dict, Any
import re

from app.ai_pipeline.state import AppState
from app.ai_pipeline.nodes.llm import llm

#----------------------------------------------------------------------
# retrieval_tools 연동
# - 실제 구현 예시는 app/ai_pipeline/retrieval/history.py 등에 둘 수 있음.
# - 여기서는 "현재 규제-제품 임베딩"을 넣으면
#   "과거 규제-제품-전략 history 리스트"를 반환하는 함수만 사용한다.
#----------------------------------------------------------------------
try:
    # 예시 인터페이스:
    # def search_history_for_strategy(
    #     query_embedding: List[float],
    #     top_k: int = 5,
    # ) -> List[Dict[str, Any]]:
    #     ...
    from app.ai_pipeline.retrieval.history import search_history_for_strategy
except Exception:
    # 아직 retrieval 모듈이 준비되지 않았거나, 로컬 테스트 환경에서는
    # 더미 함수를 사용하여 히스토리 없이도 파이프라인이 동작하도록 한다.
    def search_history_for_strategy(
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return []


#------------------------
# 설정 값
#------------------------

# retrieval_tools에서 반환한 score(유사도 기반 hybrid score)에 대한 threshold
# - score >= SIMILARITY_THRESHOLD 인 히스토리만 RAG context에 사용
SIMILARITY_THRESHOLD = 0.75

# LLM이 생성한 여러 전략 사이에서
# 너무 비슷한 문장을 제거하기 위한 자카드 유사도 threshold
JACCARD_THRESHOLD = 0.80


#------------------------
# 유틸: 토큰/유사도/파싱
#------------------------

def _simple_tokens(s: str) -> List[str]:
    """
    자카드 유사도용 간단 토크나이저.
    - 소문자 변환
    - 한글/영문/숫자/공백만 남김
    """
    s = s.lower()
    s = re.sub(r"[^0-9a-zA-Z가-힣\s]", " ", s)
    return [t for t in s.split() if t]


def _jaccard(a: str, b: str) -> float:
    """
    두 문자열의 자카드 유사도 (0~1).
    - 1에 가까울수록 토큰 집합이 유사
    """
    ta, tb = set(_simple_tokens(a)), set(_simple_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _parse_strategies(raw: str) -> List[str]:
    """
    LLM 출력에서 대응 전략 리스트만 뽑기.
    - 각 줄 하나의 전략
    - "1. ...", "2) ..." 형태의 번호 prefix 제거
    - 빈 줄 제거
    """
    strategies: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 번호 prefix 제거 (예: "1. ", "2) ")
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        if line:
            strategies.append(line)
    return strategies


#------------------------
# History 후처리 (유사도 필터링 + 프롬프트 포맷)
#------------------------

def _filter_histories_by_similarity(
    histories: List[Dict[str, Any]],
    threshold: float,
) -> List[Dict[str, Any]]:
    """
    retrieval_tools에서 가져온 history 중에서
    score(유사도 기반 hybrid score)가 threshold 이상인 것만 필터링.
    - score < threshold 인 것은 RAG context에서 제거.
    """
    filtered: List[Dict[str, Any]] = []
    for h in histories:
        score = float(h.get("score", 0.0))
        if score >= threshold:
            filtered.append(h)
    return filtered


def _format_history_for_prompt(histories: List[Dict[str, Any]]) -> str:
    """
    LLM 프롬프트에 넣을 수 있도록 히스토리 정리.
    - 규제 요약 + 제품 + 과거 대응전략 + 유사도(score)를 간단히 보여줌.
    - 너무 길어지면 규제 텍스트는 앞 부분만 사용.
    """
    if not histories:
        return "없음"

    lines: List[str] = []
    for i, h in enumerate(histories, start=1):
        strategy = (h.get("strategy") or "").strip()
        if not strategy:
            continue

        reg_snippet = (h.get("regulation_text") or "").strip()
        if len(reg_snippet) > 120:
            reg_snippet = reg_snippet[:117] + "..."

        products = h.get("products") or []
        score = float(h.get("score", 0.0))

        lines.append(
            f"{i}. [유사도: {score:.2f}] "
            f"(규제 요약: {reg_snippet or 'N/A'}) "
            f"(제품: {', '.join(products) if products else 'N/A'}) "
            f"→ 과거 대응 전략: {strategy}"
        )
    return "\n".join(lines) if lines else "없음"


#------------------------
# 메인 LangGraph 노드
#------------------------

def generate_strategy_node(state: AppState) -> Dict[str, Any]:
    """
    [LangGraph 노드 엔트리 포인트]

    입력 (AppState):
        - regulation_text: 현재 규제 원문
        - regulation_effective_date: 규제 시행일
        - mapped_products: 매핑된 제품 리스트
        - regulation_product_embedding: 현재 규제-제품 매핑 임베딩
          (map_products 노드의 출력값)

    처리 흐름:
        1) 현재 규제-제품 임베딩(state.regulation_product_embedding)을
           retrieval_tools.search_history_for_strategy 에 전달하여
           VectorDB에 저장된 과거 (규제-제품-전략) history 검색
        2) history의 hybrid score(유사도)가 threshold 이상인 것만 남김
        3) 해당 history를 context로 LLM 프롬프트 구성
        4) LLM으로부터 현재 규제에 대한 대응 전략 후보 생성
        5) 라인별 전략 파싱 후, 서로 과도하게 유사한 문장은 자카드 기반으로 정리
        6) {"strategies": List[str]} 형태로 반환 (State.merge 대상)

    출력:
        {"strategies": List[str]}
    """
    regulation_text = state.regulation_text or ""
    mapped_products = state.mapped_products or []
    effective_date = (state.regulation_effective_date or "").strip()

    # map_products 노드에서 채워준 규제-제품 임베딩
    # 실제 AppState 필드명이 다르면 아래 한 줄만 맞게 수정하면 됨.
    query_embedding = getattr(state, "regulation_product_embedding", None)

    #------------------------------------------------------------------
    # 1) retrieval_tools를 통한 history 검색
    #   - 이 시점에서 dense/sparse/metadata 서칭 로직은 모두
    #     search_history_for_strategy 내부에 캡슐화되어 있음.
    #   - generate_strategy_node는 "히스토리 소비자" 역할만 수행.
    #------------------------------------------------------------------
    raw_histories: List[Dict[str, Any]] = []
    if query_embedding:
        raw_histories = search_history_for_strategy(
            query_embedding=query_embedding,
            top_k=5,
        )

    #------------------------------------------------------------------
    # 2) 유사도 threshold 적용
    #------------------------------------------------------------------
    histories = _filter_histories_by_similarity(
        histories=raw_histories,
        threshold=SIMILARITY_THRESHOLD,
    )

    history_prompt = _format_history_for_prompt(histories) if histories else "없음"
    products_str = ", ".join(mapped_products) if mapped_products else "정보 없음"

    #------------------------------------------------------------------
    # 3) LLM 프롬프트 구성
    #   - history가 있으면: 과거 전략 재사용/보완 우선
    #   - history가 없으면: 규제/제품/시행일 기반으로 신규 전략 생성
    #   - 단, 코드 상에서는 단일 프롬프트로 처리하고,
    #     "history가 '없음'이면 신규 생성"이라는 룰을 자연어로 명시.
    #------------------------------------------------------------------
    prompt = f"""
당신은 담배 및 니코틴 제품 규제 대응 전략 전문 컨설턴트입니다.

[현재 규제 정보]
- 규제 텍스트:
{regulation_text}

- 규제 시행일: {effective_date or "정보 없음"}

[현재 대상 제품]
{products_str}

[과거 유사 규제/제품에 대한 대응 전략 히스토리]
{history_prompt}

요구사항:
1. 위 히스토리 항목이 "없음"이 아니라면,
   - 과거 대응 전략을 참고하여 현재 규제에 맞게 재사용 또는 수정·보완하세요.
2. 히스토리가 "없음"이라면,
   - 규제 텍스트와 시행일, 대상 제품 정보를 바탕으로 신규 대응 전략을 작성하세요.
3. 모든 전략 문장 안에 반드시 규제 시행일 또는 관련 기한이 직접적으로 드러나도록 작성하세요.
   - 예: "2026-01-01 시행일 이전까지", "시행일(2026-01-01)을 기준으로", "2026-06-30까지 재고를 소진" 등
4. 전략은 너무 세세하게 쪼개지지 않도록 실행 단위 중심으로 작성하며,
   필요 시 신규 전략을 추가할 수 있으나 총 개수는 10개 이내로 정리하세요.
5. 전략마다 가능하면 괄호 안에 담당 주체를 간단히 적어 주세요. (예: 생산팀, 품질팀, 마케팅, 법무팀 등)
6. 서로 내용이 거의 동일하거나 중복되는 대응 전략은 하나로 합쳐 작성하세요.

출력 형식:
- 한 줄에 하나의 전략만 작성합니다.
- 앞에 번호를 붙여도 되지만, 반드시 '1. ...', '2. ...' 형태로만 사용하세요.
- 추가 설명, 서론/결론 문장, 불릿(-, • 등)은 사용하지 마세요.
"""

    #------------------------------------------------------------------
    # 4) LLM 호출
    #------------------------------------------------------------------
    raw_output = llm.invoke(prompt)

    # LangChain ChatModel 인 경우 .content 속성에 텍스트가 있을 수 있으므로 방어
    if hasattr(raw_output, "content"):
        raw_text = raw_output.content
    else:
        raw_text = str(raw_output)

    #------------------------------------------------------------------
    # 5) 전략 파싱 + 중복 제거 (서로 너무 비슷한 문장만 필터)
    #   - history 기반 재사용을 막지 않기 위해,
    #     history와의 유사도는 체크하지 않고,
    #     "LLM이 비슷한 문장을 여러 개 낸 경우"만 정리하는 용도.
    #------------------------------------------------------------------
    generated_strategies = _parse_strategies(raw_text)

    deduped: List[str] = []
    for s in generated_strategies:
        s_clean = s.strip()
        if not s_clean:
            continue

        too_similar = False
        for es in deduped:
            if _jaccard(s_clean, es) >= JACCARD_THRESHOLD:
                too_similar = True
                break

        if not too_similar:
            deduped.append(s_clean)

    #------------------------------------------------------------------
    # 6) 결과 반환
    #------------------------------------------------------------------
    return {
        "strategies": deduped,
    }
