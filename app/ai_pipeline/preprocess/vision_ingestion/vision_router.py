"""
module: vision_router.py
description: 복잡도 기반 Vision 모델 라우팅 에이전트
author: AI Agent
created: 2025-01-14
dependencies: openai
"""

import asyncio
import logging
from typing import Dict, Any, Literal, Optional
from openai import AsyncOpenAI
from openai import RateLimitError, APIError, APITimeoutError

logger = logging.getLogger(__name__)


class VisionRouter:
    """복잡도 기반 Vision LLM 라우팅."""

    def __init__(
        self,
        api_key: str,
        model_complex: str = "gpt-4o",
        model_simple: str = "gpt-4o-mini",
        complexity_threshold: float = 0.3,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        request_timeout: int = 120,
        retry_max_attempts: int = 2,
        retry_backoff_seconds: float = 1.0,
    ):
        self.api_key = api_key
        self.model_complex = model_complex
        self.model_simple = model_simple
        self.complexity_threshold = complexity_threshold
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.retry_max_attempts = retry_max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def async_client(self) -> AsyncOpenAI:
        """비동기 OpenAI 클라이언트 (lazy 초기화)."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self.api_key, timeout=self.request_timeout)
        return self._async_client

    def route_and_extract(
        self,
        image_base64: str,
        page_num: int,
        complexity_score: float,
        system_prompt: str,
    ) -> Dict[str, Any]:
        """
        복잡도에 따라 모델 선택 후 Vision 추출 (동기, 기존 호환성 유지).

        Args:
            image_base64: Base64 인코딩된 이미지
            page_num: 페이지 번호
            complexity_score: 복잡도 점수 (0-1)
            system_prompt: LLM 시스템 프롬프트

        Returns:
            Dict: {
                "page_num": int,
                "model_used": str,
                "content": str,
                "complexity_score": float,
                "tokens_used": int
            }
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai가 설치되지 않았습니다: pip install openai")

        # 모델 선택
        if complexity_score >= self.complexity_threshold:
            model = self.model_complex
            model_label = "고성능 모델"
        else:
            model = self.model_simple
            model_label = "저비용 모델"

        logger.info(f"페이지 {page_num}: 복잡도 {complexity_score:.2f} → {model_label} ({model}) 사용")

        client = OpenAI(api_key=self.api_key, timeout=self.request_timeout)

        # Vision API 호출 (재시도 로직 포함)
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": f"Extract structure from page {page_num}.",
                                },
                            ],
                        },
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                content = response.choices[0].message.content

                return {
                    "page_num": page_num,
                    "model_used": model,
                    "content": content,
                    "complexity_score": complexity_score,
                    "tokens_used": response.usage.total_tokens,
                }
            except (RateLimitError, APITimeoutError) as e:
                if attempt < self.retry_max_attempts:
                    wait_time = self.retry_backoff_seconds * attempt
                    logger.warning(
                        f"페이지 {page_num} API 오류 (시도 {attempt}/{self.retry_max_attempts}): {e}. "
                        f"{wait_time:.1f}초 후 재시도..."
                    )
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"페이지 {page_num} API 호출 최종 실패: {e}")
                    raise
            except APIError as e:
                logger.error(f"페이지 {page_num} API 오류: {e}")
                raise

    async def route_and_extract_async(
        self,
        image_base64: str,
        page_num: int,
        complexity_score: float,
        system_prompt: str,
    ) -> Dict[str, Any]:
        """
        복잡도에 따라 모델 선택 후 Vision 추출 (비동기, 병렬 처리용).

        Args:
            image_base64: Base64 인코딩된 이미지
            page_num: 페이지 번호
            complexity_score: 복잡도 점수 (0-1)
            system_prompt: LLM 시스템 프롬프트

        Returns:
            Dict: {
                "page_num": int,
                "model_used": str,
                "content": str,
                "complexity_score": float,
                "tokens_used": int
            }
        """
        # 모델 선택 (기존 로직과 동일)
        if complexity_score >= self.complexity_threshold:
            model = self.model_complex
            model_label = "고성능 모델"
        else:
            model = self.model_simple
            model_label = "저비용 모델"

        logger.debug(f"페이지 {page_num}: 복잡도 {complexity_score:.2f} → {model_label} ({model}) 사용")

        # 비동기 Vision API 호출 (재시도 로직 포함)
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                response = await self.async_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": f"Extract structure from page {page_num}.",
                                },
                            ],
                        },
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                content = response.choices[0].message.content

                return {
                    "page_num": page_num,
                    "model_used": model,
                    "content": content,
                    "complexity_score": complexity_score,
                    "tokens_used": response.usage.total_tokens,
                }
            except (RateLimitError, APITimeoutError) as e:
                if attempt < self.retry_max_attempts:
                    wait_time = self.retry_backoff_seconds * attempt
                    logger.warning(
                        f"페이지 {page_num} API 오류 (시도 {attempt}/{self.retry_max_attempts}): {e}. "
                        f"{wait_time:.1f}초 후 재시도..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"페이지 {page_num} API 호출 최종 실패: {e}")
                    raise
            except APIError as e:
                logger.error(f"페이지 {page_num} API 오류: {e}")
                raise
