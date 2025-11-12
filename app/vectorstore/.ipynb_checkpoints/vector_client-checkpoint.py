from chromadb import PersistentClient
from dataclasses import dataclass
from typing import Sequence, Mapping
from app.config.settings import settings


@dataclass
class VectorConfig:
    persist_directory: str
    collection_name: str


class VectorClient:
    def __init__(self, client: PersistentClient, collection_name: str):
        self.client = client
        self.collection = self.client.get_or_create_collection(collection_name)

    @classmethod
    def from_settings(cls, cfg: VectorConfig | None = None) -> "VectorClient":
        cfg = cfg or VectorConfig(
            persist_directory=settings.CHROMA_DB_PATH,
            collection_name=settings.CHROMA_COLLECTION,
        )
        client = PersistentClient(path=cfg.persist_directory)
        return cls(client, cfg.collection_name)

    async def insert(self, texts, dense_embeddings, sparse_embeddings, metadatas):
        self.collection.add(
            documents=texts,
            embeddings=dense_embeddings,
            sparse_embeddings=sparse_embeddings,
            metadatas=metadatas,
            ids=[m["clause_id"] for m in metadatas],
        )

    async def query(self, **kwargs):
        return self.collection.query(**kwargs)
