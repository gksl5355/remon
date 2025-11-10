# app/vectorstore/vector_client.py

from chromadb import PersistentClient
from app.config.settings import settings


class VectorClient:
    def __init__(self):
        # 최신 방식: duckdb+parquet 자동 선택
        self.client = PersistentClient(path=settings.CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION
        )

    def insert(self, ids: list, texts: list, embeddings: list, metadatas: list):
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list, top_k: int = 5):
        return self.collection.query(
            query_embeddings=[query_embedding], n_results=top_k
        )

    def clear(self):
        """테스트용: 모든 데이터 삭제"""
        self.collection.delete(where={})
