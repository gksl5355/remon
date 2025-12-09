# chatbot/service.py
from typing import List
from .models import ChatMessage, ChatRequest, ChatTurnResult
from .llm_client import LLMClient
from .history import InMemoryHistoryStore


class ChatbotService:
    """
    순수 AI 관점의 최소 서비스:
    - 세션별 히스토리(JSON 리스트) 가져오기
    - user 메시지 추가
    - LLM 호출
    - assistant 답변 추가
    - 히스토리 저장 후 결과 반환
    """

    def __init__(
        self,
        history_store: InMemoryHistoryStore,
        llm_client: LLMClient,
        system_prompt: str | None = None,
    ) -> None:
        self.history_store = history_store
        self.llm = llm_client
        self.system_prompt = (
            system_prompt
            or "너는 규제/제품/전략 관련 질문에 한국어로 답변하는 챗봇이야."
        )

    def run_turn(self, req: ChatRequest) -> ChatTurnResult:
        # 1) 기존 히스토리 가져오기
        history: List[ChatMessage] = self.history_store.get(req.session_id)

        # 2) 새 세션이면 system 메시지 하나 넣기
        if not history:
            history.append(ChatMessage(role="system", content=self.system_prompt))

        # 3) 이번 user 메시지 추가
        history.append(ChatMessage(role="user", content=req.message))

        # 4) LLM 호출
        reply_text = self.llm.chat(history)

        # 5) assistant 메시지 추가
        history.append(ChatMessage(role="assistant", content=reply_text))

        # 6) 히스토리 저장
        self.history_store.save(req.session_id, history)

        # 7) 결과 객체로 반환
        return ChatTurnResult(
            session_id=req.session_id,
            reply=reply_text,
            history=history,
        )
