from chromadb import Client
from chromadb.config import Settings
from app.config.settings import CHROMA_DB_PATH, CHROMA_COLLECTION


class VectorClient:
    def __init__(self):
        self.client = Client(
            Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_DB_PATH)
        )
        self.collection = self.client.get_or_create_collection(name=CHROMA_COLLECTION)

    def insert(self, texts, embeddings, metadatas):
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=[str(m["clause_id"]) for m in metadatas],
        )

    def search(self, query_embedding, top_k=5):
        return self.collection.query(
            query_embeddings=[query_embedding], n_results=top_k
        )
