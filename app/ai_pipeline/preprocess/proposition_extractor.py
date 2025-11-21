"""
module: proposition_extractor.py
description: 청크에서 핵심 명제(proposition) 추출 (GPT-4o-mini 기반)
author: AI Agent
created: 2025-01-12
updated: 2025-01-12
dependencies:
    - openai, concurrent.futures
"""

from typing import List, Dict, Any
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("⚠️ openai 미설치. pip install openai 필요")


class PropositionExtractor:
    """
    청크에서 핵심 명제를 추출하는 클래스.
    
    역할:
    - GPT-4o-mini로 청크당 3-5개 핵심 명제 추출
    - 병렬 처리 (ThreadPoolExecutor, max_workers=3)
    - 폴백: 문장 분할 (LLM 실패 시)
    
    특징:
    - 법률 문서 특화 프롬프트
    - 짧은 청크는 그대로 반환
    - 에러 핸들링 (LLM 실패 시 문장 분할)
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini", max_workers: int = 3):
        """
        명제 추출기 초기화.
        
        Args:
            api_key (str): OpenAI API 키
            model (str): 사용할 모델. 기본값: "gpt-4o-mini"
            max_workers (int): 병렬 처리 워커 수. 기본값: 3
        """
        self.model = model
        self.max_workers = max_workers
        self.client = None
        
        if HAS_OPENAI and api_key:
            self.client = OpenAI(api_key=api_key)
            logger.info(f"✅ PropositionExtractor 초기화: model={model}, workers={max_workers}")
        else:
            logger.warning("⚠️ OpenAI 클라이언트 미설정. 문장 분할 모드로 동작")
    
    def extract_propositions(self, text: str) -> List[str]:
        """
        단일 텍스트에서 명제 추출.
        
        Args:
            text (str): 청크 텍스트
        
        Returns:
            List[str]: 추출된 명제 리스트 (3-5개)
        """
        if len(text) < 100:
            return [text]
        
        if not self.client:
            return self._fallback_sentence_split(text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Extract atomic factual propositions from legal text."},
                    {"role": "user", "content": f"Extract 3-5 key facts from: {text[:1500]}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            propositions = [
                p.strip() for p in response.choices[0].message.content.split('\n')
                if p.strip() and len(p.strip()) > 20
            ]
            
            return propositions[:5] if propositions else [text[:500]]
        
        except Exception as e:
            logger.debug(f"명제 추출 실패, 폴백 사용: {e}")
            return self._fallback_sentence_split(text)
    
    def extract_propositions_batch(self, chunks: List[Dict[str, Any]]) -> List[List[str]]:
        """
        여러 청크에서 명제를 병렬 추출.
        
        Args:
            chunks (List[Dict]): 청크 리스트 [{"content": "..."}, ...]
        
        Returns:
            List[List[str]]: 각 청크의 명제 리스트
        """
        if not self.client:
            logger.warning("OpenAI 미설정. 문장 분할 모드")
            return [self._fallback_sentence_split(c.get("content", "")) for c in chunks]
        
        def extract_single(chunk):
            return self.extract_propositions(chunk.get("content", ""))
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(extract_single, chunk): i for i, chunk in enumerate(chunks)}
            results = [None] * len(chunks)
            
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"청크 {idx} 명제 추출 실패: {e}")
                    results[idx] = [chunks[idx].get("content", "")[:500]]
        
        logger.info(f"✅ {len(chunks)}개 청크 명제 추출 완료")
        return results
    
    def _fallback_sentence_split(self, text: str) -> List[str]:
        """폴백: 문장 분할."""
        sentences = re.split(r'[.!?]\s+', text)
        return [s.strip() + '.' for s in sentences if len(s.strip()) > 50][:5]
