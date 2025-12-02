import os
import random
import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_URL = "https://qdrant.skala25a.project.skala-ai.com"
COLLECTION = "skala-2.4.17-regulation"
API_KEY = os.getenv("QDRANT_API_KEY", "Skala25a!23$")
HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}


def upsert_sample_point():
    # Dense vector: 1024차원
    dense_vector = [0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * (1024 - 5)
    sparse_vector = {"indices": [3, 7, 11], "values": [0.8, 0.6, 0.9]}

    payload = {
        "points": [
            {
                "id": 1,
                "vector": {
                    "dense": dense_vector,
                    "sparse": sparse_vector,
                },
                "payload": {
                    "text": "Test regulation content",
                    "ref_id": "TEST-001",
                    "regulation_id": "TEST-REG",
                    "country": "US"
                },
            }
        ]
    }

    url = f"{BASE_URL}/collections/{COLLECTION}/points?wait=true"
    resp = requests.put(url, json=payload, headers=HEADERS, verify=False, timeout=30)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    
    resp.raise_for_status()
    print("Upsert result:", resp.json())


def main():
    upsert_sample_point()


if __name__ == "__main__":
    main()
