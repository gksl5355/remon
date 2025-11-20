#======================================================================
# test_generate_strategy_single.py
# - 완전 독립 테스트 파일 (app.* import 안 함)
# - 더미 규제 / 제품 / history 전략 기반으로 LLM에 대응 전략 생성 요청
#======================================================================

import os
import textwrap
import re
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

#----------------------------------------------------------------------
# 1) .env 로드 & OpenAI 클라이언트 설정
#----------------------------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 가 .env 에 설정되어 있지 않습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)


#----------------------------------------------------------------------
# 2) 전략 파서 (_parse_strategies)
#----------------------------------------------------------------------

def parse_strategies(raw_text: str) -> List[str]:
    """
    LLM이 생성한 텍스트에서 대응 전략 문장 리스트만 추출.
    - '1.', '2)', '-', '•' 같은 번호/불릿 제거
    - 그래도 아무것도 못 뽑으면, 줄 단위로라도 다 살림
    """
    strategies: List[str] = []

    numbered_list_pattern = re.compile(r"^[0-9]{1,2}[.)]\s+")

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        cleaned = line

        # "1. xxx", "2) xxx" -> 숫자 부분 제거
        m = numbered_list_pattern.match(cleaned)
        if m:
            cleaned = cleaned[m.end():].strip()

        # 불릿 ("- xxx", "• xxx", "* xxx") 제거
        if cleaned and cleaned[0] in ("-", "•", "*"):
            cleaned = cleaned[1:].strip()

        if cleaned:
            strategies.append(cleaned)

    # 아무것도 못 뽑았으면 줄 단위로라도 살림
    if not strategies:
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if cleaned:
                strategies.append(cleaned)

    return strategies


#----------------------------------------------------------------------
# 3) LLM 프롬프트 구성 (_build_llm_prompt 축약 버전)
#----------------------------------------------------------------------

def build_llm_prompt(
    regulation_summary: str,
    products: List[str],
    history_strategies: List[str],
) -> str:
    products_block = "\n".join(f"- {p}" for p in products) if products else "- (no mapped products)"
    history_block = (
        "\n".join(f"- {s}" for s in history_strategies)
        if history_strategies
        else "- (no relevant historical strategies)"
    )

    prompt = f"""
You are a senior regulatory compliance strategy consultant
specializing in global tobacco and nicotine regulations.

Generate **actionable, product-specific compliance strategies**
based on the information below.

[REGULATION SUMMARY]
{regulation_summary.strip()}

[MAPPED PRODUCTS]
{products_block}

[REFERENCE: HISTORICAL STRATEGIES]
{history_block}

[REQUIREMENTS]
1. Provide strategies that are immediately executable actions  
   (e.g., “Establish a reformulation plan…”, “Initiate inventory withdrawal…”,  
   “Prepare updated packaging…”).

2. Consider both compliance (legal) requirements and business impact mitigation.

3. Output format: **one strategy per line**  
   (no bullets or numbering needed by the LLM; the parser will handle extraction).

4. When the regulation contains explicit numerical values  
   (e.g., nicotine concentration %, tar mg, warning label area %,  
   allowed advertising period, maximum refill volume, etc.),  
   you must reflect those numbers **exactly as stated**.  
   - Do NOT invent new numbers, percentages, limits, or thresholds.  
   - If the regulation provides no numbers, do NOT introduce any.

5. Each strategy must describe a **concrete, actionable operational task**.  
   - Examples: update packaging/labeling, conduct additional testing,  
     execute inventory depletion, adjust product formulation,  
     update online/offline product descriptions.  
   - Avoid vague principles such as “enhance compliance” or  
     “improve internal processes.” Every line must be an action  
     that a real operational team can immediately execute.

6. Use the [REFERENCE: HISTORICAL STRATEGIES] only when they are relevant.  
   - Do NOT include historical strategies that do not match the current regulation  
     or the mapped products.  
   - If proposing new strategies, they must be clearly grounded in  
     either (a) the current regulation + products, or  
     (b) patterns observed in the historical strategies.

Now generate the strategies.
"""
    return textwrap.dedent(prompt).strip()


#----------------------------------------------------------------------
# 4) 메인: 더미 데이터 + LLM 호출
#----------------------------------------------------------------------

if __name__ == "__main__":
    # 더미 규제 요약
    regulation_summary = """
니코틴 함량이 1mL 당 20mg을 초과하는 전자담배 액상은
2026년 1월 1일 이후 신규 제조 및 수입이 금지된다.
기존 재고는 2026년 6월 30일까지 소진하여야 하며,
제품 포장 전면의 30% 이상에 경고 문구를 표시해야 한다.
"""

    # 더미 매핑 제품 리스트
    mapped_products = [
        "KT&G Lil Vapor Mint 20mg",
        "KT&G Lil Vapor Classic 18mg",
    ]

    # 더미 history 전략 (Qdrant에서 온 것처럼 가정)
    history_strategies = [
        "니코틴 함량을 규제 기준 이하로 조정하기 위한 리포뮬레이션 계획을 수립한다.",
        "규제 시행일까지 기존 재고를 단계적으로 소진하기 위한 출고·프로모션 계획을 수립한다.",
        "포장 전면 경고 문구 및 경고 면적 비율을 규제 기준에 맞도록 디자인 템플릿을 업데이트한다.",
        "온라인몰 및 오프라인 매장에 규제 변경 사항과 제품 변경 일정을 사전 공지한다.",
    ]

    print("\n===== Running single-file strategy generation test =====\n")

    prompt = build_llm_prompt(
        regulation_summary=regulation_summary,
        products=mapped_products,
        history_strategies=history_strategies,
    )

    # OpenAI ChatCompletion 호출
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    raw_output_text = resp.choices[0].message.content or ""
    strategies = parse_strategies(raw_output_text)

    print("=== Generated strategies ===")
    for i, s in enumerate(strategies, start=1):
        print(f"{i}. {s}")

    # 토큰/비용 대략 확인 (원하면 주석 풀어)
    usage = resp.usage
    if usage:
        in_t = usage.prompt_tokens
        out_t = usage.completion_tokens
        tot_t = usage.total_tokens
        print("\n[Usage] input:", in_t, "output:", out_t, "total:", tot_t)

    print("\n==== DONE ====\n")
