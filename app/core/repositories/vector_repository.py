# app/core/repositories/vector_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

class VectorRepository:
    """
    VectorDB 연동 Repository
    
    책임:
    - VectorDB 읽기/쓰기 (임베딩 저장/조회)
    - PostgreSQL과의 State 동기화
    - 기술적 변환 (벡터 형식 변환)
    
    Note:
        VectorDB는 AI Pipeline이 직접 관리하므로
        Repository는 읽기 전용으로만 사용될 수도 있음
    """
    
    def __init__(self, vector_client):
        """
        Args:
            vector_client: VectorDB 클라이언트 (예: Chroma, Pinecone, Weaviate 등)
        """
        self.vector_client = vector_client
    
    async def search_similar_regulations(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        유사한 규제 문서 검색 (MappingAgent-태환용)
        
        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 최대 결과 수
            filters: 필터 조건 (예: country_code, product_category)
        
        Returns:
            유사 문서 리스트 [{"regulation_id": ..., "score": ..., "metadata": ...}]
        """
        # VectorDB에서 유사도 검색
        results = await self.vector_client.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters
        )
        
        return self._convert_vector_results(results)
    
    async def get_regulation_embedding(
        self,
        regulation_id: int
    ) -> Optional[List[float]]:
        """
        특정 규제의 임베딩 조회
        
        Args:
            regulation_id: 규제 ID
        
        Returns:
            임베딩 벡터 또는 None
        """
        # VectorDB에서 ID로 조회
        result = await self.vector_client.get(
            ids=[str(regulation_id)]
        )
        
        if result and result['embeddings']:
            return result['embeddings'][0]
        return None
    
    async def check_embedding_exists(
        self,
        regulation_id: int
    ) -> bool:
        """
        임베딩 존재 여부 확인 (RefineAgent + Embedding용)
        
        Args:
            regulation_id: 규제 ID
        
        Returns:
            존재 여부
        """
        embedding = await self.get_regulation_embedding(regulation_id)
        return embedding is not None
    
    def _convert_vector_results(self, results: Dict) -> List[Dict[str, Any]]:
        """
        기술적 변환: VectorDB 결과를 표준 형식으로 변환
        
        Args:
            results: VectorDB raw 결과
        
        Returns:
            변환된 결과 리스트
        """
        converted = []
        
        if not results or 'ids' not in results:
            return converted
        
        for i, doc_id in enumerate(results['ids'][0]):
            item = {
                'regulation_id': int(doc_id),
                'score': results['distances'][0][i] if 'distances' in results else None,
                'metadata': results['metadatas'][0][i] if 'metadatas' in results else {}
            }
            converted.append(item)
        
        return converted
