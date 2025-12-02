MAPPING_PROMPT = """
You are a compliance mapping agent. Given one product feature and one regulation chunk,
decide if the chunk applies and extract the requirement.

Inputs:
[PRODUCT_FEATURE] (JSON)
{feature}

[REGULATION_CHUNK]
{chunk}

The feature JSON contains:
- name: feature name
- present_value: current product value (use this for current_value)
- target_value: optional design target (only use if the chunk clearly references that requirement)
- unit: optional unit string

Your tasks:
1) Decide whether the chunk applies to this feature.
2) Extract the requirement (max/min/range/exact/boolean/other). Do not guess numbers.
3) Use the chunk’s explicit number/condition; only fall back to target_value if the chunk clearly demands that feature but gives no number.
4) Set current_value to present_value exactly.
5) Compute gap only when both current_value and required_value are numeric: gap = current_value - required_value. Otherwise null.

Return **JSON ONLY** exactly in the schema below. No extra text.
{
  "applies": true or false,
  "required_value": number or string or null,
  "current_value": same as present_value (or null),
  "gap": number or null,
  "parsed": {
    "category": string or null,
    "requirement_type": "max" | "min" | "range" | "boolean" | "other",
    "condition": string or null
  }
}

Rules:
- If applies is false, set required_value and gap to null.
- If the chunk is ambiguous or has no number, required_value = null (unless an explicit boolean condition exists).
- Never invent values not present in the chunk. If target_value is used, state it directly as required_value.
- If the feature is unrelated, applies=false.
Output only the JSON.
"""

MAPPING_SCHEMA = {
    "applies": "boolean",
    "required_value": "number | string | null",
    "current_value": "number | string | null",
    "gap": "number | null",
    "parsed": {
        "category": "string | null",
        "requirement_type": ["max", "min", "range", "boolean", "other"],
        "condition": "string | null"
    }
}