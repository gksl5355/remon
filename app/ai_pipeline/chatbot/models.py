# chatbot/models.py
from typing import List, Literal
from pydantic import BaseModel


class ChatMessage(BaseModel):
    """LLM에 넘길 한 개의 메시지."""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """AI 서비스 입장에서 한 턴 입력."""
    session_id: str      # 세션 식별자 (프론트/백엔드에서 관리)
    message: str         # 사용자의 새 질문


class ChatTurnResult(BaseModel):
    """한 턴 처리 결과 (AI 입장)."""
    session_id: str
    reply: str                   # 이번 assistant 답변
    history: List[ChatMessage]   # 현재까지 전체 히스토리 (JSON 리스트)
