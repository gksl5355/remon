import httpx
import numpy as np

dense = np.random.rand(1024).tolist()
sparse = {
    "indices": [10, 100, 200],
    "values": [1.0, 0.5, 0.8]
}

payload = {
    "query": {
        "vector": {
            "strategy-dense-vector": dense,
            "strategy-sparse-vector": sparse
        }
    },
    "limit": 5
}

response = httpx.post(
    "https://qdrant.skala25a.project.skala-ai.com/collections/skala-2.4.17-strategy/points/query",
    headers={
        "api-key": "Skala25a!23$",
        "User-Agent": "curl/7.81.0",
        "Content-Type": "application/json",
    },
    json=payload,
    timeout=30,
    verify=False
)

print(response.status_code, response.text)

