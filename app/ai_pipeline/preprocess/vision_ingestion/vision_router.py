"""
module: vision_router.py
description: 복잡도 기반 Vision 모델 라우팅 에이전트
author: AI Agent
created: 2025-01-14
dependencies: openai
"""

import logging
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)


class VisionRouter:
    """복잡도 기반 Vision LLM 라우팅."""

    def __init__(
        self,
        api_key: str,
        model_complex: str = "gpt-4o",
        model_simple: str = "gpt-5-nano",
        complexity_threshold: float = 0.3,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        self.api_key = api_key
        self.model_complex = model_complex
        self.model_simple = model_simple
        self.complexity_threshold = complexity_threshold
        self.max_tokens = max_tokens
        self.temperature = temperature

    def route_and_extract(
        self,
        image_base64: str,
        page_num: int,
        complexity_score: float,
        system_prompt: str,
    ) -> Dict[str, Any]:
        """
        복잡도에 따라 모델 선택 후 Vision 추출.

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
                "complexity_score": float
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

        client = OpenAI(api_key=self.api_key)

        # Vision API 호출
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
