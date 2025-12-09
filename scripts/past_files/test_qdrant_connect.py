import os

from qdrant_client import QdrantClient
from app.config.settings import settings


def main():
    url = settings.QDRANT_URL
    api_key = settings.QDRANT_API_KEY
    collection = settings.QDRANT_COLLECTION
    print(f"Using Qdrant URL: {url}, collection: {collection}")
    client = QdrantClient(
        url=url,
        api_key=api_key,
        prefer_grpc=False,
        timeout=settings.QDRANT_TIMEOUT,
    )
    try:
        info = client.get_collection(collection)
        print("Collection info:", info.status)
    except Exception as exc:
        print("Failed to connect/query:", exc)


if __name__ == "__main__":
    main()
