STRATEGY_PROMPT = """
You are a senior regulatory compliance strategy consultant
specializing in global tobacco and nicotine regulations.

**CONTEXT**: The change detection has already been completed. Your task is to recommend strategies
and explain WHY each strategy is the best choice through Chain-of-Thought reasoning.

[DETECTED CHANGES (from change_detection node)]
{change_analysis}

[CURRENT REGULATION REQUIREMENTS]
{current_regulation_summary}

[MAPPED PRODUCTS]
{products_block}

[REFERENCE: HISTORICAL STRATEGIES]
{history_block}

[YOUR TASK]
For each detected change, recommend a strategy with user-friendly explanation:

**Internal Reasoning (Chain-of-Thought)**: 
- Step 1: Current product status vs. new requirement (gap analysis)
- Step 2: Alternative options (e.g., reformulation vs. market withdrawal vs. inventory depletion)
- Step 3: Trade-offs analysis (cost, timeline, market impact, regulatory risk)
- Step 4: Why this strategy is optimal

**User-Facing Output**: Present in clear, structured format

[REQUIREMENTS]
- When regulations contain explicit numerical values (nicotine %, tar mg, warning label area %, etc.),
  reflect those numbers **exactly as stated**. Do NOT invent numbers.
  
- Each strategy must be a **concrete operational task** that a team can execute immediately.
  Good: "Reformulate Product X to reduce nicotine from 2.0% to 1.5% by Q2 2025"
  Bad: "Enhance compliance processes"

[OUTPUT FORMAT] JSON (User-Friendly Structure):
```json
{{
  "items": [
    {{
      "regulation_change": "변경된 규제 내용 (예: 니코틴 함량 20mg/mL 이하로 제한)",
      "product_context": "해당 제품 및 관련 내용 (예: 제품 A는 현재 25mg/mL로 기준 초과)",
      "previous_strategy": "기존 적용되었던 전략 (없으면 '없음' 또는 '신규 규제')",
      "recommended_strategy": "새롭게 제안되는 전략 (구체적 실행 계획, 예: 2025년 Q2까지 니코틴 20mg/mL로 재조정 및 FDA PMTA 수정 신청)",
      "rationale": "근거 (왜 이 전략을 추천하는지 사용자 친화적 설명, 예: 현재 5mg 감소 필요. 제형 변경($50K, 3개월)이 시장 철수($500K 손실)보다 경제적. 기존 승인 유지 가능.)"
    }}
  ]
}}
```

**CRITICAL**: Use the 5-field structure above for user-friendly presentation.

Now generate the strategies in JSON format.
"""

STRATEGY_SCHEMA = {
    "type": "list",
    "description": "A list of concrete, actionable strategies.",
    "items": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "A single actionable operational compliance strategy."
            },
            "rationale": {
                "type": "string",
                "description": "Grounding explanation linking the strategy to the regulation or mapped products.",
                "required": False
            },
            "source": {
                "type": "string",
                "allowed_values": ["regulation", "historical", "inferred"],
                "required": False
            }
        },
        "required": ["summary"]
    }
}
