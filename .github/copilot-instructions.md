# REMON AI Agent Instructions

## Project Overview
**REMON** is an AI-powered Regulation Monitoring & Mapping System that automatically collects, processes, and analyzes overseas regulatory documents to generate product impact assessments and response strategies.

**Core Pipeline:** Collect → Refine (OCR/Translation/Embedding) → Map Products → Score Impact → Generate Strategy → Report

## Architecture Quick Start

### Layered Architecture (Bottom-Up)
1. **Data Layer:** PostgreSQL (metadata), Chroma VectorDB (embeddings), OpenSearch (hybrid search, planned)
2. **AI Pipeline:** LangGraph-based workflow with 6 nodes: preprocess → map_products → score_impact → generate_strategy → validate_strategy → report
3. **Service Layer:** `{Collect,Refine,Mapping,Report}Service` orchestrate between API and AI Pipeline
4. **API Layer:** FastAPI routers in `/app/api/` with REST endpoints + admin endpoints
5. **Frontend:** Vue3 components consuming APIs via axios client

### Key File Structure
- **Pipeline Logic:** `/app/ai_pipeline/graph.py` (LangGraph workflow), `/app/ai_pipeline/state.py` (state schema)
- **Pipeline Nodes:** `/app/ai_pipeline/nodes/` - each node processes a state and returns dict updates
- **Services:** `/app/services/{collect,refine,mapping,report}_service.py` - call AI pipeline and DB
- **APIs:** `/app/api/{regulation,report,auth}_api.py` + `/app/api/admin/` for admin endpoints
- **Data Access:** `/app/core/{models,repositories,schemas}` follow Repository pattern with SQLAlchemy async ORM
- **VectorDB:** `/app/vectorstore/vector_client.py` manages Chroma collections with metadata (meta_country, meta_lang, etc)
- **Preprocessing:** `/app/ai_pipeline/preprocess/` handles OCR, translation, chunking, embedding via BGE-M3
- **Crawlers:** `/app/crawler/` collects regulatory sources (currently stubs, coordinates with CollectService)

## Critical Patterns

### 1. LangGraph Pipeline Node Pattern
Every node in `/app/ai_pipeline/nodes/` follows this signature:
```python
async def node_name(state: AppState) -> dict:
    """Process state and return dict with updates."""
    # Read from state
    input_data = state.get("field_name")
    # Compute (often calls LLM via langchain)
    result = await llm_chain.invoke(input_data)
    # Return dict to merge into state
    return {"output_field": result}
```
**Key:** Nodes are pure functions; state merging is handled by LangGraph framework.

### 2. Service → API → Frontend Flow
- **Services** (`/app/services/`) call async functions and coordinate DB + AI pipeline
- **APIs** inject DB session via FastAPI dependency (see `/app/core/database.py` → `get_db()`)
- **Frontend** calls REST endpoints; responses always include `status`, `data`, and optional `error`
- Example: Report generation routes through `/api/reports/{id}` → `report_api.py` → `ReportService` → AI pipeline

### 3. State Management (No Redux/Vuex)
- **Backend:** AppState (dict-based) flows through LangGraph; immutable updates only
- **Frontend:** Vue3 uses Pinia store (if present) or local `ref()` for simple state; no global Redux
- **Persistence:** DB is single source of truth; Redis optional for caching/sessions

### 4. VectorDB Metadata Convention
Chroma chunks store metadata with prefixes:
- `meta_regulation_id`, `meta_country` (e.g., "KR", "US"), `meta_lang`, `meta_date`, `meta_source`
- Chunks are country-filtered at query time; see `/app/vectorstore/vector_client.py` for search patterns

### 5. Async/Await Discipline
- **Backend:** All DB and external calls are async (SQLAlchemy AsyncSession, httpx)
- **Current LLM Policy:** Sequential/blocking (direct awaits), NOT parallel yet
- **Future:** Async batching via Redis queues if bottleneck detected
- **Frontend:** All API calls use `async/await` in Vue composables

### 6. Code Documentation Standards
#### **Docstring (Google Style)**
- **File header:** Includes module, description, author, created/updated dates, dependencies
- **Public functions/classes:** Full docstring with Args, Returns, Raises, Example
- **Internal helpers (`_` prefix):** Single-line comment or minimal docstring
- Example file header:
  ```python
  """
  module: report_service.py
  description: 리포트 생성, 조회 및 관련 비즈니스 로직을 처리하는 서비스 계층
  author: 홍길동
  created: 2025-11-07
  updated: 2025-11-07
  dependencies:
      - app.config.logger
      - app.models.report
  """
  ```
- See `/docs/CODE_COMMENT_GUIDE_v0.3.md` for full examples

#### **Logging Guidelines (NO `print()` in FastAPI code)**
- **Never use `print()`** in server code; use `logging` module instead
- Each file declares module logger at top: `logger = logging.getLogger(__name__)`
- Log levels:
  - `DEBUG`: Development/debug details only
  - `INFO`: Major state changes and core flows (operational visibility)
  - `WARNING`: Unexpected but non-fatal issues
  - `ERROR`: Specific function failures (needs investigation)
  - `CRITICAL`: System-wide failures (immediate action required)
- Always include context (user_id, report_id, filename, etc.)
- Use `logger.exception()` in except blocks to capture tracebacks
- Example: `logger.error(f"File processing failed for user_id={user_id}, filename='{filename}'.")`

#### **Type Hinting (Python 3.10+ syntax)**
- All function arguments and returns must have type hints
- Use built-in generics: `list[str]` not `List[str]`
- Use union operator: `str | None` not `Optional[str]`
- Example:
  ```python
  async def generate_report(self, data: dict) -> dict | None:
      users: list[str] = ["alice", "bob"]
      ...
  ```

### 7. Repository Pattern & ORM
- **Models:** `/app/core/models/{regulation,product,report,mapping,user}_model.py` - SQLAlchemy declarative classes
- **Repositories:** `/app/core/repositories/{regulation,product,report,mapping}_repository.py` provide CRUD methods
- **Base pattern:** All repos inherit from `base_repository.py` and provide: `find_by_id()`, `create()`, `update()`, `delete()`
- **Dependency injection:** Always receive `AsyncSession` from FastAPI dependency (see `/app/core/database.py` → `get_db()`)
- **Stateless design:** Repos are stateless functions; DB session is request-scoped
- Example usage:
  ```python
  from app.core.repositories.report_repository import ReportRepository
  from app.core.database import get_db
  
  @router.get("/reports/{report_id}")
  async def get_report(report_id: int, session: AsyncSession = Depends(get_db)):
      repo = ReportRepository()
      report = await repo.find_by_id(session, report_id)
      return report or {"error": "Not found"}
  ```

## Common Workflows

### Modifying AI Pipeline
1. **Edit node logic:** Update `/app/ai_pipeline/nodes/{node_name}.py`
2. **Change state schema:** Update `/app/ai_pipeline/state.py` (AppState dict keys)
3. **Rebuild graph:** Verify edges in `/app/ai_pipeline/graph.py` match new nodes
4. **Test:** Run `pytest tests/test_*.py` or use `/test.py` for quick validation

### Adding a New API Endpoint
1. **Create/edit router:** `/app/api/new_feature_api.py` with `APIRouter(prefix="/api/feature", tags=[...])`
2. **Inject service:** Reference service class (e.g., `ReportService`) with DB session
3. **Register router:** Add `app.include_router(...)` in `/app/main.py`
4. **Test with frontend:** Vue3 component calls `api.post("/feature/...")` (see `/frontend/src/services/api.js`)

### Adding a New Repository & Model
1. **Create model:** `/app/core/models/{entity}_model.py` using SQLAlchemy declarative syntax
2. **Create repository:** `/app/core/repositories/{entity}_repository.py` inheriting `BaseRepository`
3. **Implement CRUD:** Provide `find_by_id()`, `find_all()`, `create()`, `update()`, `delete()`
4. **Type all methods:** Use `async` for DB calls, return ORM object or `None`
5. **Write tests:** Add test in `/tests/test_repositories.py` with `@pytest.mark.asyncio`

### Querying VectorDB with Metadata Filters
```python
from app.vectorstore.vector_client import VectorClient

vc = VectorClient()
# Query by country (typical pattern)
results = vc.search(query_embedding, top_k=5)  # Returns {"metadatas": [...], "documents": [...]}
# Metadata stored as: {"meta_regulation_id": 123, "meta_country": "KR", "meta_lang": "ko", ...}
```

### Credential/Config Management
- Use `.env` file with `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `CHROMA_DB_PATH`, `CHROMA_COLLECTION`
- Loaded via `app.config.settings.Settings` (Pydantic BaseSettings)
- Never hardcode credentials; all env vars must be documented in `setup_python.sh` or `.env.example`

### Testing Strategy (Pytest)
- **Framework:** Use `pytest` with `@pytest.mark.asyncio` for async tests
- **Structure:** Follow AAA pattern (Arrange → Act → Assert)
- **Repository tests:** Mock AsyncSession dependency
- **API tests:** Use TestClient with dependency override
- **Independence:** Each test must be independent; no shared state
- Example:
  ```python
  @pytest.mark.asyncio
  async def test_generate_report_success(mock_session):
      # Arrange
      repo = ReportRepository()
      
      # Act
      report = await repo.find_by_id(mock_session, 1)
      
      # Assert
      assert report is not None
      assert report.id == 1
  ```
- Run tests: `pytest tests/` or `python test.py`

## Development Commands
- **Setup:** Run `bash setup_python.sh` (installs Python 3.11 + uv, creates venv)
- **Install deps:** `uv pip install -e .` (installs from pyproject.toml)
- **Run server:** `uvicorn app.main:app --reload` (dev) or `bash scripts/run_server.sh` (prod)
- **Start services:** Use `bash scripts/start_chroma.sh`, `start_redis.sh`, `start_opensearch.sh`
- **Tests:** `pytest tests/` or `python test.py` for quick checks
- **DB migrations:** Schema in `/scripts/schema.sql`; init with `python scripts/init_db.py`

## Performance & Data Flow
- **Embeddings:** BGE-M3 model; store vectors in Chroma only (not SQL)
- **LLM Calls:** GPT-4o mini; currently sequential (no parallel batch yet)
- **Search:** Chroma for semantic/vector; OpenSearch planned for hybrid keyword+semantic retrieval
- **Caching:** Redis optional; prioritize DB query optimization first
- **Regulation Lifecycle:** Document → OCR → Language Detect → Translate → Chunk → Embed → Map → Score → Report

## AI Pipeline Node Details

### Node I/O Specification
Each node in LangGraph reads/writes AppState (dict-based). Common state fields:

- **`input_documents`** (list[str]): Raw regulation texts
- **`translation_results`** (dict): {"ko": "...", "en": "..."} translations  
- **`embeddings`** (list[list[float]]): BGE-M3 vectors
- **`product_mappings`** (list[dict]): `{"product_id": 1, "matched_clauses": [...], "confidence": 0.95}`
- **`impact_scores`** (dict): `{"product_1": {"impact": "HIGH", "score": 0.87}}`
- **`strategy_result`** (str): Generated response strategy text
- **`validation_strategy`** (bool): True if strategy passes validation
- **`final_report`** (str): Markdown-formatted report

### Node Execution Order
1. **preprocess** → loads, chunks, detects language
2. **map_products** → queries VectorDB, matches regulations to products
3. **score_impact** → calculates impact scores via LLM
4. **generate_strategy** → LLM generates response strategies
5. **validate_strategy** → checks quality (loops back on failure)
6. **report** → formats final report with sections

## Integration Points & External Dependencies
- **FastAPI + Uvicorn:** API server framework
- **SQLAlchemy 2.0:** Async ORM for PostgreSQL
- **LangGraph >= 1.0.2 + LangChain:** AI pipeline orchestration and LLM calls
- **Sentence-Transformers (BGE-M3):** Embedding model; runs locally
- **ChromaDB 1.3.4:** Persistent vector store (DuckDB+Parquet backend)
- **OpenAI API:** GPT-4o mini for generation/translation/analysis
- **Vue3 + Axios:** Frontend client

## Database Schema Overview

### Core Tables (PostgreSQL)
- **`regulations`**: id, country, title, content, upload_date, status
- **`products`**: id, name, category, description
- **`mappings`**: id, regulation_id, product_id, matched_clauses, confidence_score
- **`reports`**: id, regulation_id, user_id, title, status, created_at, updated_at
- **`report_sections`**: id, report_id, section_type, content, order
- **`users`**: id, email, name, role (admin/user), created_at

### VectorDB Collections (Chroma)
- **Collection name:** `{CHROMA_COLLECTION}` (env-configurable)
- **Documents:** Chunked regulation text (typically 512-token chunks)
- **Metadata:** `meta_regulation_id`, `meta_country`, `meta_lang`, `meta_date`, `meta_source`, `clause_id`
- **Embeddings:** BGE-M3 1024-dimensional vectors

## Recommended Reading Order for New Contributors
1. `README.md` – Project overview and team roles
2. `/app/ai_pipeline/graph.py` – Understand the 6-node workflow
3. `/app/api/report_api.py` – Example REST endpoint structure
4. `/app/services/report_service.py` – Service layer pattern
5. `/app/core/database.py` – Database session management
6. `/docs/CODE_COMMENT_GUIDE_v0.3.md` – Code standards (logging, typing, docstrings, testing)
7. `/frontend/src/services/api.js` – Frontend-backend API contract
8. Team roles in `README.md` Section 5 to understand who owns which module

## Frontend Architecture (Vue3)

### File Structure
- **`/frontend/src/pages/`** – Main page components (RegulatoryDashboard, ReportViewer, AdminPanel)
- **`/frontend/src/components/`** – Reusable UI components (tables, forms, charts)
- **`/frontend/src/services/api.js`** – Axios instance + interceptors for API calls
- **`/frontend/src/router/`** – Vue Router routes (admin routes, user routes)
- **`/frontend/src/store/`** – Pinia store (optional; currently using local `ref()`)

### API Client Pattern
```javascript
// src/services/api.js
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api", // FastAPI backend
  timeout: 5000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: auto-inject JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 errors
api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401) alert("로그인이 필요합니다.");
  return Promise.reject(error);
});

export default api;
```

### Vue3 Composable Pattern (State Management)
```javascript
// Use local ref() instead of global Redux/Vuex
import { ref, computed } from "vue";
import api from "@/services/api";

export function useReports() {
  const reports = ref([]);
  const loading = ref(false);
  const error = ref(null);

  const fetchReports = async () => {
    loading.value = true;
    try {
      const res = await api.get("/reports");
      reports.value = res.data;
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  };

  return { reports, loading, error, fetchReports };
}
```

## Common Gotchas
- **Async/await:** All DB calls must be awaited; forgetting `await` causes hanging coroutines
- **State immutability:** Modify LangGraph state by returning dicts; don't mutate in-place
- **Session scope:** DB sessions are request-scoped in FastAPI; don't cache or reuse across requests
- **VectorDB filters:** Current implementation is basic; metadata queries may need custom logic
- **LLM retry logic:** Network errors to OpenAI not yet implemented; handle in calling service
- **Country codes:** Always use ISO 2-letter codes (e.g., "KR", "US", "EU" for Europe)


## 명령에 충실하게 코드를 작성하는 방식을 가장 중심으로 작업을 진행할것
## 채팅 프롬프트는 모두 한글로 설명할것
## 작업중 컨텍스트를 넘어선 디렉토리에서 작업을 진행하는경우 곧바로 진행하지말고 이유와 범위를 먼저 말할 것
## 내가 내리는 모든 코드수정명령을 받은 경우, 계획과 이유, 범위를 포함해 설명해서 먼저 답변을 주고 진행관련한 명령을 받은경우 진행할것
## 요약 문서 작업은 만들때 파일명에 버전을 꼭 붙혀서 만들고 이전버전과 헷갈리지 않도록 할것 이전버전의 내용과 중복을 피하고 바뀐내용 중심으로 만들것 그리고 .github 디렉토리에 만들것

