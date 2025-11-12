from chromadb import PersistentClient
from dataclasses import dataclass
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
        cfg = VectorConfig(
            persist_directory=settings.CHROMA_DB_PATH,
            collection_name=settings.CHROMA_COLLECTION,
        )
        client = PersistentClient(path=cfg.persist_directory)
        return cls(client, cfg.collection_name)

    async def insert(self, texts, embeddings, metadatas):
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=[m["clause_id"] for m in metadatas],
        )

    async def query(self, *, query_dense, query_sparse=None, alpha: float = 0.7,
                  n_results: int = 5, where: dict | None = None):
    kwargs = {"query_embeddings": [query_dense], "n_results": n_results}
    if query_sparse is not None:
      kwargs["query_sparse_embeddings"] = [query_sparse]
      kwargs["alpha"] = alpha              # dense 0.7 / sparse 0.3 가중
    if where:
      kwargs["where"] = where              # 메타데이터 필터
    return self.collection.query(**kwargs)
