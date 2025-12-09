# chatbot/llm_client.py
import os
from typing import List
from openai import OpenAI
from .models import ChatMessage


class LLMClient:
    """히스토리(JSON 리스트)를 받아 OpenAI에 요청하는 얇은 래퍼."""

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def chat(self, messages: List[ChatMessage]) -> str:
        """
        messages: role/content 구조의 전체 히스토리
        return: 이번 assistant의 텍스트 응답
        """
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[m.model_dump() for m in messages],
        )
        return completion.choices[0].message.content
