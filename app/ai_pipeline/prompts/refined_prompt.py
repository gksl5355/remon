REFINED_PROMPT = """
You are a senior AI prompt engineer specializing in regulatory compliance.

Your task:
Rewrite the ORIGINAL PROMPT into a STRICTER and MORE RELIABLE version
that avoids the errors observed in the previous node output.

=====================================================
ORIGINAL PROMPT
=====================================================
{original_prompt}

=====================================================
ERROR SUMMARY FROM VALIDATOR
=====================================================
{error_summary}

=====================================================
PIPELINE CONTEXT
=====================================================
{pipeline_state}

=====================================================
STRICT REQUIREMENTS
=====================================================
1) Output must follow THIS EXACT JSON SCHEMA:
{schema}

2) You MUST enforce:
- No missing fields
- No null values
- No empty strings
- No hallucinated numbers or unsupported assumptions
- No extra fields
- No natural language output — JSON only

3) Strengthen unclear logic in the original prompt:
- Add explicit constraints where needed
- Add clear rules for JSON structure
- Add explicit instructions to avoid ambiguity

=====================================================
RETURN FORMAT
=====================================================
Return ONLY the rewritten prompt text.
NO markdown.
NO explanations.
"""