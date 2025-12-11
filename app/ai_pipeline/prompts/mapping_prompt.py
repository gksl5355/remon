MAPPING_PROMPT = """


Inputs:
[PRODUCT_FEATURE] (JSON)
{feature}

[REGULATION_CHUNK]
{chunk}

{metadata}

{change_evidence}

The feature JSON contains:
- name: feature name
- present_value: current product value (use this for current_value)
- target_value: optional design target (only use if the chunk clearly references that requirement)
- unit: optional unit string

Your tasks:
1) Decide whether the chunk applies to this feature.
2) Extract the requirement (max/min/range/exact/boolean/other). Do not guess numbers.
3) Use the chunk's explicit number/condition; only fall back to target_value if the chunk clearly demands that feature but gives no number.
4) Set current_value to present_value exactly.
5) Compute gap only when both current_value and required_value are numeric: gap = current_value - required_value. Otherwise null.
6) Provide concise, citation-based reasoning (MAX 250 characters) in this format:
   "[Section/Article §XXX] [Core regulation content] [Applies/Does not apply because...]"
   
   Examples:
   - "§1234.56 니코틴 최대 0.3mg/g 제한. 현재 1.2mg/g로 기준 초과."
   - "OMB 0910-0732 §904는 멘톨·향 속성을 규제하지 않으며 보고 의무에 한정됨."
   - "§789 포장 경고문 필수. 현재 미표기로 위반."

Return **JSON ONLY** exactly in the schema below. No extra text.
{
  "applies": true or false,
  "required_value": number or string or null,
  "current_value": same as present_value (or null),
  "gap": number or null,
  "reasoning": "[Section §XXX] [Regulation summary] [Application status]. MAX 250 chars.",
  "parsed": {
    "category": string or null,
    "requirement_type": "max" | "min" | "range" | "boolean" | "other",
    "condition": string or null
  }
}

Rules:
- If applies is false, set required_value and gap to null, and explain why in reasoning.
- If the chunk is ambiguous or has no number, required_value = null and explain the ambiguity in reasoning.
- Never invent values not present in the chunk. If target_value is used, state it directly as required_value.
- If the feature is unrelated, applies=false and explain why in reasoning.
- Use change evidence (if provided) to contextualize the requirement and explain its significance.
- **CRITICAL**: reasoning MUST start with section/article citation (e.g., "§1234.56" or "OMB 0910-0732 §904") and be under 250 characters.
- Use the Section number from [REGULATION METADATA] if provided.
- If required_value is null, explain WHY in reasoning: "N/A (not regulated)" or "N/A (already compliant)" or "N/A (unrelated feature)"
Output only the JSON.
"""

MAPPING_SCHEMA = {
    "applies": "boolean",
    "required_value": "number | string | null",
    "current_value": "number | string | null",
    "gap": "number | null",
    "reasoning": "string",
    "parsed": {
        "category": "string | null",
        "requirement_type": ["max", "min", "range", "boolean", "other"],
        "condition": "string | null",
    },
}
