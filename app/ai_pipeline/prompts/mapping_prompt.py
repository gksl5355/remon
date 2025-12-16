MAPPING_PROMPT = """## CRITICAL INSTRUCTIONS

### 1. Semantic Relevance Validation (MANDATORY FIRST CHECK)
**BEFORE analyzing the chunk, verify semantic alignment:**

- Current Feature: {feature_name}
- Expected Keywords: [from SEMANTIC VALIDATION CONTEXT]
- Chunk Keywords: [extract from chunk text]

**STRICT REJECTION CRITERIA:**
IF chunk discusses a DIFFERENT topic than the feature:
  → applies=false
  → reasoning="N/A (unrelated): §{section} addresses {chunk_topic}, not {feature_name}"

**Examples:**
- Feature="nicotine" + Chunk="§1160.5 Warning labels must be 50% of package"
  → applies=false, reasoning="N/A (unrelated): §1160.5 addresses label size, not nicotine content"

- Feature="label_size" + Chunk="§1160.3 Nicotine limit 0.3mg/g"
  → applies=false, reasoning="N/A (unrelated): §1160.3 addresses nicotine limits, not label dimensions"

- Feature="battery" + Chunk="§1160.7 Flavor prohibitions"
  → applies=false, reasoning="N/A (unrelated): §1160.7 addresses flavors, not battery specifications"

**Only proceed to detailed analysis if semantic match is confirmed.**

---

## CRITICAL: Semantic Relevance Validation
If SEMANTIC VALIDATION CONTEXT is provided:

1. **Feature-Chunk Alignment Check**:
   - Current Feature: {feature_name}
   - Expected Keywords: [provided list]
   - Chunk Keywords: [extract from chunk text]
   
2. **Validation Rules**:
   ✓ VALID: Chunk discusses the SAME topic as feature
      Example: Feature="nicotine" + Chunk="nicotine concentration limit 20mg/ml"
   
   ✗ INVALID: Chunk discusses DIFFERENT topic
      Example: Feature="nicotine" + Chunk="warning label must cover 50% of package"
      → applies=false, reasoning="semantic_mismatch: chunk discusses labels, not nicotine"

3. **Decision Logic**:
   IF (chunk keywords ∩ expected keywords) == EMPTY:
      → applies=false
      → reasoning="semantic_mismatch: feature={feature_name}, chunk_topic={detected_topic}"
   ELSE:
      → Proceed with normal mapping logic

**Example Rejection**:
Feature: "nicotine"
Chunk: "§1160.5 Warning labels must be at least 50% of package surface"
Keywords: ["warning", "label", "package", "surface"]
Expected: ["nicotine", "mg/ml", "concentration"]
→ applies=false, reasoning="semantic_mismatch: chunk discusses packaging labels, not nicotine content"

### 2. Multiple Candidates Analysis
You may receive MULTIPLE regulation chunks for the SAME feature.
- Analyze EACH chunk independently
- Only mark applies=true if the chunk DIRECTLY regulates this specific feature
- If a chunk is procedural/testing-only (e.g., "ISO testing required"), mark applies=false with reasoning="procedural_only"

---




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

**CRITICAL MATCHING RULES (applies=true ONLY IF):**
1. The chunk DIRECTLY regulates THIS SPECIFIC feature's value/condition/requirement
2. The chunk contains EXPLICIT numerical limits, mandatory conditions, or prohibitions for THIS feature
3. The feature name appears in the chunk AND the chunk sets a compliance requirement for it

**applies=false IF:**
- The chunk only mentions the feature keyword but does NOT regulate it (e.g., reporting obligations, definitions, exemptions)
- The chunk regulates a DIFFERENT aspect (e.g., "nicotine" in labeling requirements when feature is nicotine content)
- The chunk is about procedural/administrative matters (reporting, record-keeping, notifications)
- The feature is mentioned in examples, background, or non-binding context
- The regulation applies to a different product category or jurisdiction

**Additional Rules:**
- If applies is false, set required_value and gap to null, and explain why in reasoning.
- If the chunk is ambiguous or has no number, required_value = null and explain the ambiguity in reasoning.
- Never invent values not present in the chunk. If target_value is used, state it directly as required_value.
- Use change evidence (if provided) to contextualize the requirement and explain its significance.
- **CRITICAL**: reasoning MUST start with section/article citation (e.g., "§1234.56" or "OMB 0910-0732 §904") and be under 250 characters.
- Use the Section number from [REGULATION METADATA] if provided.
- If required_value is null, explain WHY in reasoning: "N/A (not regulated)" or "N/A (already compliant)" or "N/A (unrelated feature)" or "N/A (procedural only)"

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
