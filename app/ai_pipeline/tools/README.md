# RAG Retrieval Tools

규제 문서 VectorDB(Qdrant) 검색을 위한 고급 RAG Retrieval Tool 모음.

---

## 📁 파일 구조

```
app/ai_pipeline/tools/
├── __init__.py                    # 패키지 초기화
├── retrieval_config.py            # 설정 관리
├── retrieval_strategies.py        # 검색 전략 (5가지)
├── retrieval_tool.py              # 메인 Tool (LangChain 호환)
├── retrieval_utils.py             # 유틸리티 함수
├── filter_builder.py              # 동적 필터 빌더
├── retrieval_optimizer.py         # 성능 최적화
└── README.md                      # 이 파일
```

---

## 🚀 빠른 시작

### 1. 기본 사용법

```python
from app.ai_pipeline.tools import RegulationRetrievalTool

# Tool 초기화
tool = RegulationRetrievalTool()

# 검색 실행
result = await tool.search(
    query="nicotine content limit tobacco products",
    strategy="hybrid",
    top_k=5,
    filters={"meta_country": "US"}
)

# 결과 확인
for item in result.results:
    print(f"[{item['rank']}] {item['text'][:100]}...")
    print(f"Score: {item['scores']['final_score']:.2f}")
```

---

## 🎯 검색 전략

### 1. Dense (의미 검색)
```python
result = await tool.search(
    query="warning label requirements",
    strategy="dense",
    top_k=5
)
```

### 2. Hybrid (Dense + Sparse)
```python
result = await tool.search(
    query="FDA enforcement tobacco",
    strategy="hybrid",
    alpha=0.7,  # Dense 가중치 (0~1)
    top_k=5
)
```

### 3. Metadata First (필터 우선)
```python
result = await tool.search(
    query="cigarette regulations",
    strategy="metadata_first",
    filters={
        "meta_country": "US",
        "meta_jurisdiction": "federal",
        "meta_regulation_type": "tobacco_control"
    }
)
```

### 4. Parent-Child (명제 → 부모 청크)
```python
result = await tool.search(
    query="nicotine limit",
    strategy="parent_child",
    return_parent=True  # 부모 청크 포함
)

# 부모 청크 접근
for item in result.results:
    if item.get("parent_chunk"):
        print(f"부모 청크: {item['parent_chunk']['text']}")
```

### 5. Hierarchical (계층 구조 활용)
```python
result = await tool.search(
    query="section 101 requirements",
    strategy="hierarchical",
    top_k=5
)
```

---

## 🔧 필터 빌더

### 1. 기본 필터 빌더
```python
from app.ai_pipeline.tools import FilterBuilder

filters = (FilterBuilder()
    .with_country("US")
    .with_jurisdiction("federal")
    .with_regulation_type("tobacco_control")
    .with_date_range(days_ago=365)
    .build())
```

### 2. 제품 기반 필터
```python
from app.ai_pipeline.tools import ProductFilterBuilder

product = {
    "export_country": "KR",
    "category": "cigarette"
}

filters = (ProductFilterBuilder()
    .from_product(product)
    .build())

# 결과: {"meta_country": "KR", "meta_regulation_type": "tobacco_control"}
```

### 3. 고급 필터
```python
from app.ai_pipeline.tools import AdvancedFilterBuilder

filters = (AdvancedFilterBuilder()
    .with_any_of_countries(["US", "KR", "EU"])
    .with_recent_regulations(days=180)
    .exclude_sections(["SEC. 999"])
    .build())
```

---

## ⚡ 성능 최적화

### 1. 캐싱
```python
from app.ai_pipeline.tools import QueryCache

cache = QueryCache(max_size=1000, ttl_seconds=3600)

# 캐시 조회
cached = cache.get(query, filters)
if cached:
    return cached

# 검색 실행
result = await tool.search(query, filters=filters)

# 캐시 저장
cache.set(query, filters, result)
```

### 2. 배치 검색
```python
from app.ai_pipeline.tools import BatchRetriever

retriever = BatchRetriever(tool, max_concurrent=5)

queries = [
    {"query": "nicotine limit", "filters": {"meta_country": "US"}},
    {"query": "warning label", "filters": {"meta_country": "KR"}},
    {"query": "FDA enforcement", "filters": {"meta_country": "US"}}
]

results = await retriever.batch_search(queries)
```

### 3. 임베딩 배치 처리
```python
from app.ai_pipeline.tools import EmbeddingBatcher

batcher = EmbeddingBatcher(embedding_pipeline, batch_size=32)

texts = ["text1", "text2", ..., "text100"]
embeddings = await batcher.batch_embed(texts)
```

---

## 🔗 노드 통합 예시

### map_products 노드에서 사용
```python
from app.ai_pipeline.tools import get_retrieval_tool, ProductFilterBuilder

class MapProductsNode:
    def __init__(self):
        self.retrieval_tool = get_retrieval_tool()
    
    async def run(self, state: AppState):
        products = await self.fetch_products()
        
        for product in products:
            # 제품별 필터 생성
            filters = (ProductFilterBuilder()
                .from_product(product, state.metadata)
                .build())
            
            # 검색 실행
            result = await self.retrieval_tool.search(
                query=self._build_query(product),
                strategy="hybrid",
                filters=filters,
                top_k=5
            )
            
            # State 업데이트
            state.retrieved_contexts = result.results
            state.retrieval_metadata = result.metadata
        
        return state
```

---

## 📊 State 통합

### AppState 필드
```python
class AppState(BaseModel):
    # RAG 검색 결과
    retrieved_contexts: Optional[List[Dict[str, Any]]] = None
    retrieval_metadata: Optional[Dict[str, Any]] = None
```

### 검색 결과 구조
```python
retrieved_contexts = [
    {
        "id": "doc_FDA_2025_00397_chunk_0_prop_3",
        "rank": 1,
        "text": "명제 텍스트...",
        "scores": {
            "final_score": 0.87,
            "dense_score": 0.85,
            "sparse_score": 0.72,
            "hybrid_score": 0.83
        },
        "metadata": {
            "meta_country": "US",
            "meta_jurisdiction": "federal",
            "meta_regulation_type": "tobacco_control",
            ...
        },
        "parent_chunk": {  # return_parent=True 시
            "id": "doc_FDA_2025_00397_chunk_0",
            "text": "전체 청크 텍스트...",
            "section": "SEC. 101"
        }
    }
]

retrieval_metadata = {
    "strategy": "hybrid",
    "filters_applied": {"meta_country": "US"},
    "num_results": 5,
    "search_time_ms": 45.2
}
```

---

## 🧪 테스트

```bash
# 단위 테스트 실행
pytest app/tests/test_retrieval_tool.py -v

# 특정 테스트만 실행
pytest app/tests/test_retrieval_tool.py::TestRetrievalTool::test_search_with_filters -v
```

---

## 📝 설정

### retrieval_config.py
```python
from app.ai_pipeline.tools import RetrievalConfig

config = RetrievalConfig(
    default_strategy="hybrid",
    default_top_k=5,
    default_alpha=0.7,
    return_parent_by_default=False,
    enable_caching=False,
    verbose=False
)

tool = RegulationRetrievalTool(config=config)
```

---

## 🔍 디버깅

### 로깅 활성화
```python
import logging

logging.getLogger("app.ai_pipeline.tools").setLevel(logging.DEBUG)
```

### 검색 메타데이터 확인
```python
result = await tool.search(query="test")

print(result.metadata)
# {
#   "strategy": "hybrid",
#   "filters_applied": {...},
#   "num_results": 5,
#   "search_time_ms": 45.2,
#   "query_text": "test"
# }
```

---

## 🚨 주의사항

1. **벡터는 State에 저장하지 않음** (메모리 효율)
2. **필터는 Node에서 생성** (Tool은 수동적)
3. **비동기 함수 사용** (`await tool.search()`)
4. **캐싱은 선택적** (기본 비활성화)

---

## 📚 참고 자료

- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)
- [Qdrant Filtering](https://qdrant.tech/documentation/concepts/filtering/)
- [BGE-M3 Model](https://huggingface.co/BAAI/bge-m3)
