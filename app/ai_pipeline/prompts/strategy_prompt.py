STRATEGY_PROMPT = """
You are a senior regulatory compliance strategy consultant
specializing in global tobacco and nicotine regulations.

Generate **actionable, product-specific compliance strategies**
based on the information below.

[REGULATION SUMMARY]
{regulation_summary}

[MAPPED PRODUCTS]
{products_block}

[REFERENCE: HISTORICAL STRATEGIES]
{history_block}

[REQUIREMENTS]
1. Provide strategies that are immediately executable actions  
   (e.g., "Establish a reformulation plan…", "Initiate inventory withdrawal…",  
   "Prepare updated packaging…").

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
   - Avoid vague principles such as "enhance compliance" or  
     "improve internal processes." Every line must be an action  
     that a real operational team can immediately execute.

6. Use the [REFERENCE: HISTORICAL STRATEGIES] only when they are relevant.  
   - Do NOT include historical strategies that do not match the current regulation  
     or the mapped products.  
   - If proposing new strategies, they must be clearly grounded in  
     either (a) the current regulation + products, or  
     (b) patterns observed in the historical strategies.

Now generate the strategies.
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
