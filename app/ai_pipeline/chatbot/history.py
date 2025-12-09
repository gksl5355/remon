# chatbot/history.py
from typing import Dict, List
from .models import ChatMessage


class InMemoryHistoryStore:
    """
    AI 입장에서 '세션 → 메시지 리스트'만 관리하는 최소 구현체.
    나중에 필요하면 이 부분만 DB로 교체하면 됨.
    """

    def __init__(self) -> None:
        # session_id -> [ChatMessage, ...]
        self._store: Dict[str, List[ChatMessage]] = {}

    def get(self, session_id: str) -> List[ChatMessage]:
        """세션 히스토리 전체 반환 (없으면 빈 리스트)."""
        return self._store.get(session_id, []).copy()

    def save(self, session_id: str, messages: List[ChatMessage]) -> None:
        """세션 히스토리 저장."""
        self._store[session_id] = messages.copy()
