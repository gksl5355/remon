#======================================================================
# app/ai_pipeline/nodes/generate_strategy.py
# 대응 전략
# RAG 이전 규제 대응 history 반영 
# input - 
# output - strategies: List[str]
#======================================================================

from typing import List, Dict
import re
from app.ai_pipeline.state import AppState                     # AppState.strategies: List[str]
from app.ai_pipeline.nodes.llm import llm         

#------------------
# 설정
#------------------
JACCARD_THRESHOLD = 0.80

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

    # 너무 짧은 건 의미 없는 경우가 많음
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
        term = _clean_action_line(ln)

        # 다시 한 번 공백 제거
        term = term.strip()
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

    # 2) 부분집합 관계 (조금 더 세부화된 같은 전략으로 간주)
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
# 프롬프트 템플릿 (규제 + 제품 + 히스토리 기반 → 최종 전략)
#-----------------------------------------------
def _render_strategy_prompt(
    regulation_text: str,
    mapped_products: List[str],
    rag_context_docs: List[str],
) -> str:

    products_block = ", ".join(mapped_products or [])
    history_block = "\n".join(f"- {c}" for c in (rag_context_docs or [])[:5]) or "- (검색된 근거 없음)"

    return f"""
[ROLE]
당신은 담배/니코틴 제품 규제 대응 전문가입니다.
아래의 정보(규제/제품/검색된 근거)를 종합하여
실제 실행 가능한 수준의 '최종 대응 전략'을 제시하십시오.

[기준 규제 조항]
{regulation_text}

[대상 제품]
{products_block}

[검색된 근거 (과거 유사 규제/제품/전략 히스토리)]
{history_block}

[지시사항]

1. 반드시 다음 세 가지 정보만 근거로 사용하십시오.
   - [기준 규제 조항]
   - [대상 제품]
   - [검색된 근거 (과거 유사 규제/제품/전략 히스토리)]

2. 특히, [기준 규제 조항]에 명시된 수치 기준
   (예: 니코틴 함량 %, 타르 mg, 경고문 면적 %, 광고 금지 기간 등)이 있을 경우
   해당 수치를 그대로 반영하십시오.
   - 새로운 수치, 비율, 기준을 임의로 만들지 마십시오.
   - 규제에 수치가 없으면, 수치를 만들어내지 말고 질적/행위적 전략만 제시하십시오.

3. 각 항목은 하나의 '실행 단위 업무'를 나타내야 합니다.
   - 예: 라벨/패키지 수정, 시험·검사 재실시, 재고 소진 계획, 온라인몰 설명 업데이트 등
   - 단순한 원칙 수준(예: "규제 준수 강화", "내부 프로세스 정비")의 모호한 표현은 피하고,
     실제로 담당자가 바로 실행할 수 있는 구체적인 액션으로 작성하십시오.

4. 과거 [검색된 근거]에 등장하는 대응 전략을 우선 참고하되,
   이번 규제 상황에 맞지 않는 전략은 포함하지 마십시오.
   새로운 전략을 제안하는 경우에도
   반드시 [기준 규제 조항] 또는 [검색된 근거]에서 근거를 찾을 수 있어야 합니다.

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


#----------------------------------
# 메인 노드 (generate_strategy_node)
#----------------------------------

def generate_strategy_node(state: AppState) -> Dict:
    """
    규제 텍스트 + 매핑 제품 + RAG 히스토리를 기반으로
    최종 대응 전략을 한 번에 생성한다.
    """

    # 0) 입력
    regulation_text = getattr(state, "regulation_text", "") or ""
    mapped_products = getattr(state, "mapped_products", []) or []
    rag_context_docs = getattr(state, "rag_context_docs", []) or []

    if not regulation_text:
        state.strategies = []
        return {"strategies": state.strategies}

    # 1) 프롬프트 생성 & LLM 호출
    prompt = _render_strategy_prompt(
        regulation_text=regulation_text,
        mapped_products=mapped_products,
        rag_context_docs=rag_context_docs,
    )

    raw = llm.invoke(prompt)

    # 2) LLM 결과 파싱
    candidates = _parse_llm_actions(raw)

    # 후보가 비었으면 보충 요청
    if not candidates:
        raw2 = llm.invoke(prompt + "\n반드시 불릿 형식으로 3~7개의 대응 전략을 출력하십시오.")
        candidates = _parse_llm_actions(raw2)

    # 3) 중복 제거
    deduped = _dedup_by_jaccard(candidates, threshold=JACCARD_THRESHOLD)

    state.strategies = deduped

    # 4) LangGraph 반환 
    return {"strategies": state.strategies}