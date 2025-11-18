#======================================================================
# app/ai_pipeline/nodes/generate_strategy.py
# 대응 전략
# - 규제 + 제품 조합 임베딩으로 Qdrant history 검색
# - 과거 규제/제품/전략 텍스트를 프롬프트에 넣어 LLM으로 최종 전략 생성
# - 생성된 전략을 다시 Qdrant history에 저장
# input  - state.regulation_text, state.mapped_products
# output - strategies: List[str]
#======================================================================

from typing import List, Dict, Optional
import os
import re
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from app.ai_pipeline.state import AppState                     # AppState.strategies: List[str]
from app.ai_pipeline.nodes.llm import llm
from app.ai_pipeline.nodes.embedding import embed_text         # str -> List[float]

#------------------
# 설정
#------------------
JACCARD_THRESHOLD = 0.80

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
HISTORY_COLLECTION = os.getenv("QDRANT_HISTORY_COLLECTION", "regulation_strategy_history")
HISTORY_TOP_K = int(os.getenv("HISTORY_TOP_K", "5"))

_qdrant_client: Optional[QdrantClient] = None


def _get_qdrant_client() -> QdrantClient:
    """
    Qdrant 클라이언트 lazy singleton.
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY or None,
        )
    return _qdrant_client


#------------------------
# 유틸: 토큰/유사도/파싱
#------------------------
def _simple_tokens(s: str) -> List[str]:
    """
    자카드 유사도용 간단 토크나이저.
    - 소문자 변환
    - 한글/영문/숫자/공백/일부 기호(-,%,/,~)만 남김
    """
    s = s.lower()
    s = re.sub(r"[^0-9a-zA-Z가-힣\s\-\%\/~]", " ", s)
    return [t for t in s.split() if t]


def _tokens_set(s: str) -> set:
    return set(_simple_tokens(s))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens_set(a), _tokens_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _clean_action_line(line: str) -> str:
    """
    LLM 출력 한 줄에서 불릿/번호만 제거하고 본문은 최대한 보존.
    예)
    - 기존 재고 2026-06-30까지 소진 계획 수립
    1) 제품 포트폴리오 조정한다.
    ② 경고 문구 라벨 부착
    """
    if not line:
        return ""

    line = line.strip()
    if not line:
        return ""

    # 앞쪽 불릿: -, *, • 등 제거
    line = re.sub(r"^[-*•●]+", "", line).strip()

    # 숫자+점 or 숫자+괄호 형식 제거: 1. / 1) / ① 등
    line = re.sub(r"^[0-9]+[.)]\s*", "", line).strip()
    line = re.sub(r"^[①-⑳]\s*", "", line).strip()

    return line


def _is_valid_action_text(text: str) -> bool:
    """
    '대응 전략'으로 쓸 수 있는지만 가볍게 체크.
    - 길이 너무 짧은 경우 제외
    - [ROLE], [지시사항] 같은 메타/헤더 제외
    - 나머지는 구어체/서술형/명사구 상관없이 허용
    """
    if not text:
        return False

    if len(text) < 3:
        return False

    # 대괄호 헤더 형태 ([ROLE], [OUTPUT FORMAT] 등) 제거
    if text.startswith("[") and text.endswith("]"):
        return False

    # 메타 텍스트로 자주 나오는 프리픽스 제거
    lowered = text.lower()
    meta_prefixes = (
        "role:", "system:", "assistant:", "user:",
        "지시사항", "출력 형식", "예시", "참고"
    )
    if any(lowered.startswith(p) for p in meta_prefixes):
        return False

    return True


def _parse_llm_actions(text: str) -> List[str]:
    """
    LLM 응답에서 각 줄을 '대응 전략' 후보로 파싱.
    - 불릿/번호 제거 후 내용이 남으면 전략으로 사용
    - 명사형/서술형 구분 없이 허용
    - 날짜(2026-01-01), 수치(20 mg/mL, 30%) 등 포함 문장도 그대로 살림
    """
    items: List[str] = []

    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue

        # 불릿/번호 제거
        term = _clean_action_line(ln).strip()
        if not term:
            continue

        if _is_valid_action_text(term):
            items.append(term)

    # 혹시라도 한 줄도 못 뽑았으면, 전체 텍스트를 하나의 전략으로라도 사용
    if not items:
        text = (text or "").strip()
        if text:
            items = [text]

    return items


def _is_semantically_duplicate(a: str, b: str, threshold: float) -> bool:
    """
    두 대응 전략이 '사실상 같은 전략'인지 판단:
    1) 자카드 유사도 >= threshold
    2) 혹은 한쪽 토큰 집합이 다른 쪽의 부분집합 (상위/하위 전략 관계)
    """
    ta, tb = _tokens_set(a), _tokens_set(b)
    if not ta or not tb:
        return False

    # 1) 자카드 유사도 기준
    j = len(ta & tb) / len(ta | tb)
    if j >= threshold:
        return True

    # 2) 부분집합 관계
    if ta.issubset(tb) or tb.issubset(ta):
        return True

    return False


def _dedup_by_jaccard(lines: List[str], threshold: float = JACCARD_THRESHOLD) -> List[str]:
    """
    자카드 + 부분집합 기준으로 중복 제거.
    - 앞에서 나온 전략을 우선적으로 유지
    - 의미적으로 같은/상위-하위 관계 전략은 하나만 남김
    """
    kept: List[str] = []
    for cand in lines:
        dup = False
        for prev in kept:
            if _is_semantically_duplicate(cand, prev, threshold):
                dup = True
                break
        if not dup:
            kept.append(cand)
    return kept


#-----------------------------------------------
# 규제 + 제품 컨텍스트 블록
#  - history 검색용 임베딩에도 이 문자열 포맷을 그대로 쓰는 걸 권장
#-----------------------------------------------
def _build_regulation_product_block(
    regulation_text: str,
    mapped_products: List[str],
) -> str:
    """
    규제 + 제품을 하나의 의미 단위 텍스트로 묶는다.
    - 이 블록을 그대로 embed() 해서
      '규제+제품' 조합 임베딩으로 사용할 수 있음.
    """
    products_block = ", ".join(mapped_products or []) or "(매핑된 제품 없음)"

    return f"""
[규제]
{regulation_text}

[대상 제품]
{products_block}
""".strip()


#-----------------------------------------------
# Qdrant history 검색 (규제+제품 임베딩 기반)
#-----------------------------------------------
def _format_history_hit(payload: Dict, idx: int) -> str:
    """
    Qdrant에서 가져온 한 개의 history payload를
    generate_strategy 프롬프트에 넣기 좋은 문자열로 변환.
    """
    reg_text = payload.get("regulation_text", "")
    prod_text = payload.get("product_text", "")
    strategies = payload.get("strategy_list", []) or []
    strategies_block = "\n".join(f"- {s}" for s in strategies)

    country = payload.get("country")
    reg_id = payload.get("reg_id")

    header_meta = []
    if country:
        header_meta.append(f"국가: {country}")
    if reg_id:
        header_meta.append(f"규제 ID: {reg_id}")
    header_line = " / ".join(header_meta) if header_meta else ""

    return f"""
=== 과거 유사 사례 {idx} ===
[과거 규제]
{reg_text}

[당시 대상 제품]
{prod_text}

[당시 대응 전략]
{strategies_block}

{header_line}
""".strip()


def _search_history_blocks(
    regulation_text: str,
    mapped_products: List[str],
) -> List[str]:
    """
    현재 규제 + 매핑된 제품을 기반으로
    Qdrant history 컬렉션에서 유사 사례를 검색하고,
    프롬프트에 바로 쓸 수 있는 문자열 리스트를 반환.
    """
    # 규제 없으면 검색 안 함
    if not regulation_text:
        return []

    # 1) 쿼리 텍스트 → 임베딩
    query_text = _build_regulation_product_block(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
    )
    query_vec = embed_text(query_text)

    # 2) Qdrant 검색
    client = _get_qdrant_client()

    hits = client.search(
        collection_name=HISTORY_COLLECTION,
        query_vector=query_vec,
        limit=HISTORY_TOP_K,
        with_payload=True,
        score_threshold=None,  # 필요하면 값 지정
    )

    # 3) payload → 문자열로 변환
    docs: List[str] = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        doc_str = _format_history_hit(payload, idx=i)
        docs.append(doc_str)

    return docs


#-----------------------------------------------
# 프롬프트 템플릿 (규제 + 제품 + 히스토리 기반 → 최종 전략)
#-----------------------------------------------
def _render_strategy_prompt(
    regulation_text: str,
    mapped_products: List[str],
    history_blocks: List[str],
) -> str:

    # 규제+제품 블록 (→ 이 포맷을 임베딩에도 사용)
    current_case_block = _build_regulation_product_block(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
    )

    if history_blocks:
        history_block = "\n\n".join(history_blocks)
    else:
        history_block = "(검색된 근거 없음)"

    return f"""
[ROLE]
당신은 담배/니코틴 제품 규제 대응 전문가입니다.
아래의 정보(현재 규제/대상 제품/과거 유사 사례)를 종합하여
실제 실행 가능한 수준의 '최종 대응 전략'을 제시하십시오.

[현재 규제 + 대상 제품]
{current_case_block}

[과거 유사 규제/제품/전략 히스토리]
{history_block}

[지시사항]

1. 반드시 다음 세 가지 정보만 근거로 사용하십시오.
   - [현재 규제 + 대상 제품]
   - [과거 유사 규제/제품/전략 히스토리]
   - 일반적인 상식 수준의 규제 컴플라이언스 지식
     (단, 구체적인 수치/기한/비율은 반드시 주어진 텍스트에서만 가져오십시오.)

2. 특히, [규제]에 명시된 수치 기준
   (예: 니코틴 함량 %, 타르 mg, 경고문 면적 %, 광고 금지 기간 등)이 있을 경우
   해당 수치를 그대로 반영하십시오.
   - 새로운 수치, 비율, 기준을 임의로 만들지 마십시오.
   - 규제에 수치가 없으면, 수치를 만들어내지 말고 질적/행위적 전략만 제시하십시오.

3. 각 항목은 하나의 '실행 단위 업무'를 나타내야 합니다.
   - 예: 라벨/패키지 수정, 시험·검사 재실시, 재고 소진 계획, 온라인몰 설명 업데이트 등
   - 단순한 원칙 수준(예: "규제 준수 강화", "내부 프로세스 정비")의 모호한 표현은 피하고,
     실제로 담당자가 바로 실행할 수 있는 구체적인 액션으로 작성하십시오.

4. 과거 [과거 유사 규제/제품/전략 히스토리]에 등장하는 대응 전략을 우선 참고하되,
   이번 규제 상황과 제품 특성에 맞지 않는 전략은 포함하지 마십시오.
   새로운 전략을 제안하는 경우에도
   반드시 [현재 규제 + 대상 제품] 또는 [과거 유사 규제/제품/전략 히스토리]에서
   근거를 찾을 수 있어야 합니다.

5. 출력 형식:
   - 최종 대응 전략 리스트를 출력합니다.
   - 일반적으로 3~7개의 항목을 불릿(-, 1., 1) 등) 형식으로 출력합니다.
   - 각 항목은 명사구 또는 짧은 서술형 문장이어도 됩니다.
     예: "- 니코틴 함량을 20 mg/mL 이하로 조정한다.",
         "- 2026-06-30까지 기존 재고를 소진하기 위한 판매 프로모션을 설계한다."

[출력 형식 예시]
- 니코틴 함량을 20 mg/mL 이하로 조정한다.
- 2026-06-30까지 기존 재고 소진 계획을 수립한다.
- 제품 포장 전면 30% 이상에 경고 문구를 표기하도록 디자인을 수정한다.
- 온라인몰 및 오프라인 매장에 규제 변경 사항을 안내한다.
""".strip()


#-----------------------------------------------
# history 저장 (이번 규제 + 제품 + 생성된 전략)
#-----------------------------------------------
def _persist_history(
    regulation_text: str,
    mapped_products: List[str],
    strategies: List[str],
    extra_meta: Optional[Dict] = None,
) -> None:
    """
    현재 규제 + 매핑 제품 + 생성된 전략을
    '규제+제품+전략' 텍스트로 합쳐서 임베딩 → Qdrant에 upsert.
    """
    if not regulation_text or not strategies:
        return

    reg_prod_block = _build_regulation_product_block(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
    )
    strategy_block = "\n".join(f"- {s}" for s in strategies)

    full_text = f"""
[규제 + 대상 제품]
{reg_prod_block}

[최종 대응 전략]
{strategy_block}
""".strip()

    vec = embed_text(full_text)

    payload: Dict = {
        "regulation_text": regulation_text,
        "product_text": ", ".join(mapped_products or []),
        "strategy_list": strategies,
        "source_type": "generated",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    if extra_meta:
        payload.update(extra_meta)

    client = _get_qdrant_client()
    client.upsert(
        collection_name=HISTORY_COLLECTION,
        points=[
            qm.PointStruct(
                id=None,      # 자동 ID; 필요하면 규칙적으로 부여
                vector=vec,
                payload=payload,
            )
        ],
    )


#----------------------------------
# 메인 노드 (generate_strategy_node)
#----------------------------------
def generate_strategy_node(state: AppState) -> Dict:
    """
    [한 노드에서 모두 처리]
    - 규제 텍스트 + 매핑 제품 → 임베딩
    - Qdrant history에서 유사 사례 검색 (벡터 기반)
    - 과거 규제/제품/전략을 LLM 프롬프트에 넣고
      현재 규제에 대한 최종 대응 전략을 생성
    - 생성된 전략을 다시 Qdrant history에 저장
    """

    regulation_text = getattr(state, "regulation_text", "") or ""
    mapped_products = getattr(state, "mapped_products", []) or []

    if not regulation_text:
        state.strategies = []
        # history 없더라도 필드만 맞춰둠
        state.rag_context_docs = []
        return {"strategies": state.strategies}

    # 1) Qdrant history 검색 (규제+제품 임베딩 기반)
    history_blocks = _search_history_blocks(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
    )

    # 디버깅/추적용으로 state에도 저장해두면 LangGraph에서 보기 좋음
    state.rag_context_docs = history_blocks

    # 2) 프롬프트 생성 & LLM 호출
    prompt = _render_strategy_prompt(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
        history_blocks=history_blocks,
    )

    raw = llm.invoke(prompt)

    # 3) LLM 결과 파싱
    candidates = _parse_llm_actions(raw)

    # 후보가 비었으면 보충 요청
    if not candidates:
        raw2 = llm.invoke(
            prompt
            + "\n\n반드시 불릿 형식으로 3~7개의 대응 전략을 출력하십시오."
        )
        candidates = _parse_llm_actions(raw2)

    # 4) 중복 제거
    deduped = _dedup_by_jaccard(candidates, threshold=JACCARD_THRESHOLD)

    state.strategies = deduped

    # 5) 이번 규제+제품+전략을 history에 저장
    try:
        _persist_history(
            regulation_text=regulation_text,
            mapped_products=mapped_products,
            strategies=deduped,
            # 필요하면 state에서 country/reg_id 같은 메타데이터를 넘겨도 됨
            # extra_meta={"country": state.country, "reg_id": state.reg_id}
        )
    except Exception:
        # history 저장 실패는 전체 파이프라인을 깨뜨릴 필요는 없으니
        # 로그만 남기고 무시할 수도 있음 (여기선 그냥 무시)
        pass

    return {"strategies": state.strategies}
