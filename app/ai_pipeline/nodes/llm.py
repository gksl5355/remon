import os
from typing import Any

from openai import OpenAI


class StrategyLLM:
    """
    Minimal wrapper around the official OpenAI SDK that mimics the subset of
    LangChain's ChatOpenAI interface used inside generate_strategy_node.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for strategy generation")

        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = float(os.getenv("TEMPERATURE", "0.0"))

    def invoke(self, prompt: str) -> Any:
        """
        Compatible with the previous llm.invoke signature used by
        generate_strategy_node. Returns the raw string content from the chat
        completion response to keep downstream parsing logic unchanged.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


llm = StrategyLLM()
