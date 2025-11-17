"""
module: bm25_indexer.py
description: BM25 기반 키워드 검색 인덱스 구축 및 검색 (Chroma VectorDB 연동 전 예비)
author: AI Agent
created: 2025-11-12
updated: 2025-11-12
dependencies:
    - app.config.logger, app.ai_pipeline.preprocess.config
    - rank_bm25 (설치 필요: pip install rank-bm25)
    - typing, json, re
"""

from typing import List, Dict, Tuple, Any, Optional
import logging
import re
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

# BM25 라이브러리 (선택적)
try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    logger.warning("⚠️ rank_bm25 미설치. pip install rank-bm25 필요")


class BM25Indexer:
    """
    BM25 기반 키워드 검색 인덱스를 구축하고 검색하는 클래스.
    
    역할:
    - 규제 문서를 토크나이징 (공백 & 한글 형태소 분리)
    - BM25 통계 계산 (IDF, term frequency)
    - 키워드 검색 (상위 K개 관련 청크 반환)
    - 메타데이터와 함께 Chroma에 저장할 데이터 준비
    
    특징:
    - 한글, 영문 혼합 지원
    - 불용어 자동 제거
    - 검색 점수 반환 (후보 랭킹 용)
    """
    
    # 영문 불용어 (최소한)
    ENGLISH_STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "are", "am", "be", "been",
        "have", "has", "do", "does", "did", "will", "would", "should", "could",
        "may", "might", "must", "can", "this", "that", "these", "those", "i",
        "you", "he", "she", "it", "we", "they", "what", "which", "who", "when",
        "where", "why", "how", "if", "so", "not", "no", "yes", "about", "than"
    }
    
    # 한글 불용어 (최소한)
    KOREAN_STOPWORDS = {
        "이다", "있다", "하다", "되다", "말이다", "이", "저", "것", "수", "등",
        "때", "경우", "같", "중", "또는", "그리고", "만", "더", "없", "어떤",
        "이런", "저런", "한", "어느", "어떻게", "어디", "누구", "누가", "무엇",
        "왜", "언제", "어떤", "그", "그것", "어떤것", "무엇인지", "뭔지",
        "있다", "없다", "그", "그것", "것들", "수", "등", "약", "등등",
    }
    
    def __init__(self, k1: float = 1.5, b: float = 0.75, chunk_size: int = 512):
        """
        BM25 인덱서 초기화.
        
        Args:
            k1 (float): BM25 k1 파라미터 (term frequency 가중치). 기본값: 1.5
            b (float): BM25 b 파라미터 (문서 길이 정규화). 기본값: 0.75
            chunk_size (int): 인덱싱할 청크 크기 (문자 단위). 기본값: 512
        """
        self.k1 = k1
        self.b = b
        self.chunk_size = chunk_size
        
        # 인덱싱 데이터
        self.chunks: List[str] = []  # 청크 리스트
        self.tokenized_chunks: List[List[str]] = []  # 토크나이징된 청크
        self.chunk_metadata: List[Dict[str, Any]] = []  # 메타데이터
        self.bm25_model: Optional[BM25Okapi] = None
        
        logger.info(f"✅ BM25 인덱서 초기화: k1={k1}, b={b}, chunk_size={chunk_size}")
    
    def build_index(self, document_text: str, document_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        문서를 청크로 분할하고 BM25 인덱스를 구축합니다.
        
        Args:
            document_text (str): 규제 문서 텍스트
            document_metadata (Dict[str, Any]): 문서 메타데이터
                {
                    "doc_id": "123",
                    "title": "제목",
                    "country": "KR",
                    "language": "ko",
                    "publication_date": "2025-01-12",
                    ...
                }
        
        Returns:
            Dict[str, Any]: {
                "num_chunks": 청크 개수,
                "chunk_metadata": 청크별 메타데이터 리스트,
                "index_stats": {"avg_tokens_per_chunk": ..., "total_tokens": ...}
            }
        
        Raises:
            ValueError: 입력 텍스트가 비어있을 경우
        """
        if not document_text or not document_text.strip():
            raise ValueError("Document text cannot be empty")
        
        # 청크 분할
        chunks = self._chunk_document(document_text)
        logger.debug(f"문서 청크 분할: {len(chunks)}개")
        
        # 각 청크 토크나이징
        tokenized = []
        all_tokens = []
        for chunk in chunks:
            tokens = self._tokenize(chunk)
            tokenized.append(tokens)
            all_tokens.extend(tokens)
        
        # BM25 모델 구축
        if HAS_BM25:
            self.bm25_model = BM25Okapi(tokenized)
            logger.debug("✅ BM25 모델 구축 완료")
        else:
            logger.warning("⚠️ BM25 미설치. 검색 기능 미지원")
        
        # 메타데이터 구성
        self.chunks = chunks
        self.tokenized_chunks = tokenized
        self.chunk_metadata = []
        
        for idx, (chunk, tokens) in enumerate(zip(chunks, tokenized)):
            meta = {
                "chunk_id": f"{document_metadata.get('doc_id', 'unknown')}_{idx}",
                "doc_id": document_metadata.get("doc_id"),
                "chunk_index": idx,
                "text": chunk,
                "num_tokens": len(tokens),
                "meta_title": document_metadata.get("title", "제목 미확인"),
                "meta_country": document_metadata.get("country", "UNKNOWN"),
                "meta_language": document_metadata.get("language", "en"),
                "meta_date": document_metadata.get("publication_date"),
                "meta_category": document_metadata.get("category", "general"),
                "meta_regulation_type": document_metadata.get("regulation_type", "regulation"),
            }
            self.chunk_metadata.append(meta)
        
        # 통계
        avg_tokens = sum(len(t) for t in tokenized) / len(tokenized) if tokenized else 0
        total_tokens = sum(len(t) for t in tokenized)
        
        result = {
            "num_chunks": len(chunks),
            "chunk_metadata": self.chunk_metadata,
            "index_stats": {
                "avg_tokens_per_chunk": round(avg_tokens, 2),
                "total_tokens": total_tokens,
                "num_unique_tokens": len(set(all_tokens)),
            }
        }
        
        logger.info(
            f"✅ 인덱스 구축 완료: {len(chunks)}개 청크, "
            f"평균 토큰 {avg_tokens:.1f}개, 총 토큰 {total_tokens}개"
        )
        return result
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        BM25를 사용하여 쿼리와 관련된 청크를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            top_k (int): 반환할 상위 K개 결과. 기본값: 5
        
        Returns:
            List[Tuple[int, float, Dict[str, Any]]]: [
                (chunk_index, bm25_score, chunk_metadata),
                ...
            ]
            - chunk_index: 청크 인덱스
            - bm25_score: BM25 유사도 점수 (0~100)
            - chunk_metadata: 청크 메타데이터
        
        Raises:
            RuntimeError: BM25 모델이 구축되지 않은 경우
        """
        if not HAS_BM25 or self.bm25_model is None:
            raise RuntimeError("BM25 인덱스가 구축되지 않았습니다. build_index()를 먼저 호출하세요.")
        
        if not self.chunks:
            raise RuntimeError("빈 인덱스에서 검색할 수 없습니다.")
        
        # 쿼리 토크나이징
        query_tokens = self._tokenize(query)
        logger.debug(f"검색 쿼리 토크나이징: {query_tokens}")
        
        # BM25 검색
        scores = self.bm25_model.get_scores(query_tokens)
        
        # 상위 K개 선택
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for chunk_idx, score in ranked:
            results.append((
                chunk_idx,
                round(score, 4),  # BM25 점수
                self.chunk_metadata[chunk_idx] if chunk_idx < len(self.chunk_metadata) else {}
            ))
        
        logger.debug(f"검색 결과: {len(results)}개 청크 반환")
        return results
    
    def batch_search(self, queries: List[str], top_k: int = 5) -> List[List[Tuple[int, float, Dict]]]:
        """
        여러 쿼리를 배치로 검색합니다.
        
        Args:
            queries (List[str]): 검색 쿼리 리스트
            top_k (int): 각 쿼리당 반환할 상위 K개
        
        Returns:
            List[List[Tuple]]: 검색 결과 리스트
        """
        all_results = []
        for query in queries:
            try:
                results = self.search(query, top_k=top_k)
                all_results.append(results)
            except RuntimeError as e:
                logger.error(f"검색 실패 (쿼리: '{query}'): {e}")
                all_results.append([])
        
        logger.info(f"✅ {len(queries)}개 쿼리 배치 검색 완료")
        return all_results
    
    def _chunk_document(self, text: str) -> List[str]:
        """
        문서를 겹치지 않는 청크로 분할합니다.
        
        문장 경계 고려 (마침표, 개행 기준).
        """
        chunks = []
        current_chunk = ""
        
        # 문장 단위 분할
        sentences = re.split(r'(?<=[.!?\n])\s+', text)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _tokenize(self, text: str) -> List[str]:
        """
        텍스트를 토크나이징합니다 (한글 & 영문 혼합).
        
        불용어 제거 + 소문자 정규화.
        """
        # 소문자 정규화
        text = text.lower()
        
        # 한글 토큰화 (공백 & 형태소 기반, 간단함)
        # 실제로는 KoNLPy 또는 Mecab 사용 권장
        korean_pattern = r"[가-힣]{2,}"  # 한글 단어 (2글자 이상)
        korean_tokens = re.findall(korean_pattern, text)
        
        # 한글 불용어 제거
        korean_tokens = [t for t in korean_tokens if t not in self.KOREAN_STOPWORDS]
        
        # 영문 토큰화
        english_pattern = r"\b[a-z]{2,}\b"  # 영문 단어 (2글자 이상)
        english_tokens = re.findall(english_pattern, text)
        
        # 영문 불용어 제거
        english_tokens = [t for t in english_tokens if t not in self.ENGLISH_STOPWORDS]
        
        # 숫자 토큰 (1~3자리)
        number_tokens = re.findall(r"\d{1,3}", text)
        
        # 결합 및 중복 제거
        all_tokens = korean_tokens + english_tokens + number_tokens
        
        # 최대 토큰 길이 제한 (인덱싱 효율)
        unique_tokens = list(dict.fromkeys(all_tokens))[:100]  # 상위 100개
        
        return unique_tokens
    
    def export_for_chroma(self) -> List[Dict[str, Any]]:
        """
        Chroma VectorDB에 저장할 형식으로 변환합니다.
        
        Returns:
            List[Dict[str, Any]]: [
                {
                    "id": "doc_123_0",
                    "text": "청크 텍스트",
                    "metadata": {
                        "meta_doc_id": "123",
                        "meta_chunk_index": 0,
                        "meta_country": "KR",
                        "meta_language": "ko",
                        "meta_category": "healthcare",
                        "meta_regulation_type": "law",
                        "meta_date": "2025-01-12",
                        "bm25_tokens": ["의료", "기기", ...],
                    }
                },
                ...
            ]
        """
        chroma_docs = []
        
        for chunk_idx, (chunk_text, tokens, metadata) in enumerate(
            zip(self.chunks, self.tokenized_chunks, self.chunk_metadata)
        ):
            chroma_doc = {
                "id": metadata.get("chunk_id", f"chunk_{chunk_idx}"),
                "text": chunk_text,
                "metadata": {
                    "meta_doc_id": metadata.get("doc_id"),
                    "meta_chunk_index": chunk_idx,
                    "meta_title": metadata.get("meta_title"),
                    "meta_country": metadata.get("meta_country"),
                    "meta_language": metadata.get("meta_language"),
                    "meta_category": metadata.get("meta_category"),
                    "meta_regulation_type": metadata.get("meta_regulation_type"),
                    "meta_date": metadata.get("meta_date"),
                    "bm25_tokens": tokens[:20],  # 상위 20개 토큰만 저장
                },
            }
            chroma_docs.append(chroma_doc)
        
        logger.info(f"✅ Chroma 내보내기: {len(chroma_docs)}개 청크")
        return chroma_docs
    
    def get_statistics(self) -> Dict[str, Any]:
        """인덱스 통계를 반환합니다."""
        if not self.chunks:
            return {"status": "empty", "num_chunks": 0}
        
        token_counts = [len(tokens) for tokens in self.tokenized_chunks]
        
        return {
            "status": "indexed",
            "num_chunks": len(self.chunks),
            "avg_tokens_per_chunk": round(sum(token_counts) / len(token_counts), 2) if token_counts else 0,
            "total_tokens": sum(token_counts),
            "num_unique_tokens": len(set(t for tokens in self.tokenized_chunks for t in tokens)),
        }
