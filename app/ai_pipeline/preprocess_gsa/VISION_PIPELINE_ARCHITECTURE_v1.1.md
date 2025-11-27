# Vision-Centric Preprocessing Pipeline 아키텍처 문서 v1.1

**작성일**: 2025-11-26
**버전**: 1.1 (v1.0 대비 실제 구현 반영)  
**작성자**: AI Agent

---

## 📋 v1.1 주요 변경사항

- ✅ Vision 모델명 수정: `gpt-5-nano` → `gpt-4o-mini` (실제 OpenAI API 모델명)
- ✅ Qdrant 이중 저장 모드 추가: Docker + 로컬 동시 저장
- ✅ KTNG 내부 데이터 처리 섹션 추가
- ✅ LangSmith 설정 시점 명시
- ✅ 실제 존재하지 않는 스크립트 제거
- ✅ 출력 파일 저장 관련 내용 제거 (현재 미구현)

---

## 📋 목차

1. [개요](#개요)
2. [전체 아키텍처](#전체-아키텍처)
3. [디렉토리 구조](#디렉토리-구조)
4. [파이프라인 흐름](#파이프라인-흐름)
5. [주요 모듈 상세](#주요-모듈-상세)
6. [KTNG 내부 데이터 처리](#ktng-내부-데이터-처리)
7. [데이터 흐름](#데이터-흐름)
8. [실행 방법](#실행-방법)

---

## 개요

### 목적
규제 문서의 복잡한 표와 구조를 정확히 인식하기 위해 **LLM Vision 모델**을 활용하는 전처리 파이프라인입니다.

### 핵심 특징
- **비용 최적화**: 표 복잡도 기반 GPT-4o/4o-mini 자동 라우팅
- **능동적 분석**: 문서 첫 3페이지 분석으로 전략 수립
- **Dual Indexing**: Qdrant(Vector) + NetworkX(Graph) 동시 저장
- **이중 저장**: Docker Qdrant + 로컬 Qdrant 동시 저장
- **완전한 추적**: LangSmith 연동으로 비용/성능 모니터링

### 기술 스택
| 구분 | 기술 | 용도 |
|------|------|------|
| PDF 렌더링 | pypdfium2 | PDF → 고해상도 이미지 |
| 표 감지 | pdfplumber | 페이지 복잡도 분석 |
| Vision LLM | GPT-4o / GPT-4o-mini | 이미지 → 구조화 텍스트 |
| 청킹 | langchain-text-splitters | Markdown 계층 기반 분할 |
| 임베딩 | BGE-M3 (FlagEmbedding) | Dense + Sparse 벡터 |
| VectorDB | Qdrant | 하이브리드 검색 (Docker + 로컬) |
| Graph | NetworkX | 지식 그래프 (인메모리) |
| 추적 | LangSmith | 비용/성능 모니터링 |

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Vision Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Phase 1: Vision Ingestion                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   PDF    │→ │  Image   │→ │Complexity│→ │  Vision  │  │
│  │ Renderer │  │ (300 DPI)│  │ Analyzer │  │  Router  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│       ↓              ↓              ↓              ↓       │
│  pypdfium2      Base64        pdfplumber    GPT-4o/mini   │
│                                                             │
│  Phase 2: Semantic Processing                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │Hierarchy │→ │ Context  │→ │   Dual   │                │
│  │ Chunker  │  │ Injector │  │ Indexer  │                │
│  └──────────┘  └──────────┘  └──────────┘                │
│       ↓              ↓              ↓                       │
│  Markdown       Parent Info    Qdrant(Docker+Local)       │
│                                                             │
│  Phase 3: Graph Building (Optional)                        │
│  ┌──────────┐  ┌──────────┐                               │
│  │ Entity   │→ │  Graph   │                               │
│  │Extractor │  │ Manager  │                               │
│  └──────────┘  └──────────┘                               │
│       ↓              ↓                                      │
│  Entities       NetworkX                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
app/ai_pipeline/preprocess/
├── __init__.py                      # LangGraph 노드 진입점
├── config.py                        # 설정 관리 (Vision, Qdrant, LangSmith)
├── embedding_pipeline.py            # BGE-M3 임베딩 생성
├── vision_orchestrator.py           # 전체 파이프라인 조율
│
├── vision_ingestion/                # Phase 1: Vision 기반 추출
│   ├── __init__.py
│   ├── pdf_renderer.py              # pypdfium2 이미지 렌더링
│   ├── complexity_analyzer.py       # pdfplumber 표 감지
│   ├── vision_router.py             # GPT-4o/mini 라우팅 Agent
│   ├── structure_extractor.py       # LLM 출력 → Pydantic 검증
│   └── document_analyzer.py         # 문서 규칙 분석 Agent (첫 3페이지)
│
├── semantic_processing/             # Phase 2: 청킹 & 인덱싱
│   ├── __init__.py
│   ├── hierarchy_chunker.py         # Markdown 계층 기반 청킹
│   ├── context_injector.py          # 부모 계층 정보 주입
│   └── dual_indexer.py              # Qdrant + Graph 동시 저장
│
├── graph_builder/                   # Phase 3: 지식 그래프
│   ├── __init__.py
│   ├── entity_extractor.py          # 엔티티/관계 추출
│   └── graph_manager.py             # NetworkX 그래프 관리
│
└── ktng_internal/                   # KTNG 내부 데이터 처리
    ├── __init__.py
    ├── ktng_pdf_parser.py           # KTNG PDF 파싱
    ├── ktng_chunking_strategy.py    # 규제-제품 결합 청킹
    └── ktng_embedding_processor.py  # 별도 컬렉션 저장
```

---

## 파이프라인 흐름

### 1. 진입점 (Entry Point)

```python
# LangGraph에서 호출
from app.ai_pipeline.preprocess import preprocess_node

state = {
    "preprocess_request": {
        "pdf_paths": ["/path/to/regulation.pdf"],
        "use_vision_pipeline": True  # ← Vision Pipeline 활성화
    }
}

# 실행
result = await preprocess_node(state)
```

### 2. Phase 1: Vision Ingestion

**목적**: PDF → 이미지 → Vision LLM → 구조화된 Markdown

#### 2.1 PDF 렌더링 (`pdf_renderer.py`)
```python
renderer = PDFRenderer(dpi=300)
rendered_pages = renderer.render_pages(pdf_path)
# Output: [{"page_num": 1, "image_base64": "...", "width": 2480, "height": 3508}]
```

#### 2.2 문서 분석 (`document_analyzer.py`) - 능동적 전략 수립
```python
# 첫 3페이지로 문서 규칙 파악
doc_analysis = document_analyzer.analyze(first_3_images)
# Output: {
#   "document_type": "US Federal Regulation",
#   "hierarchy_pattern": "Part > Section",
#   "recommended_strategy": "Use GPT-4o for tables"
# }
```

#### 2.3 복잡도 분석 (`complexity_analyzer.py`)
```python
complexity = complexity_analyzer.analyze_page(pdf_path, page_num)
# Output: {
#   "has_table": True,
#   "complexity_score": 0.85,  # 0-1
#   "table_count": 3
# }
```

#### 2.4 Vision 라우팅 (`vision_router.py`) - 비용 최적화
```python
# 복잡도 기반 모델 선택
if complexity_score >= 0.3:
    model = "gpt-4o"        # 복잡한 표
else:
    model = "gpt-4o-mini"   # 단순 텍스트

extraction = vision_router.route_and_extract(
    image_base64=image,
    page_num=page_num,
    complexity_score=complexity_score
)
# Output: {
#   "page_num": 1,
#   "model_used": "gpt-4o",
#   "content": "# Part 1\\n## Section 1.1\\n...",
#   "tokens_used": 1234
# }
```

#### 2.5 구조 추출 (`structure_extractor.py`) - Pydantic 검증
```python
structure = structure_extractor.extract(llm_output, page_num)
# Output: PageStructure(
#   page_num=1,
#   markdown_content="# Part 1\\n...",
#   entities=[ExtractedEntity(name="FDA", type="Organization")],
#   tables=[ExtractedTable(headers=["Item", "Limit"], rows=[...])]
# )
```

---

### 3. Phase 2: Semantic Processing

**목적**: Markdown → 계층 청킹 → 컨텍스트 주입 → Qdrant 저장

#### 3.1 계층 청킹 (`hierarchy_chunker.py`)
```python
chunker = HierarchyChunker(max_tokens=1024)
chunks = chunker.chunk_document(markdown_text, page_num)
# Output: [
#   {
#     "text": "Section 1.1 content...",
#     "metadata": {"page_num": 1, "Part": "Part 1", "Section": "Section 1.1"},
#     "hierarchy": ["Part 1", "Section 1.1"],
#     "token_count": 512
#   }
# ]
```

**청킹 전략**:
1. **1차 분할**: MarkdownHeaderTextSplitter로 `#`, `##`, `###` 기준 분할
2. **토큰 체크**: tiktoken으로 1024 토큰 초과 여부 확인
3. **2차 분할**: 초과 시 RecursiveCharacterTextSplitter로 재분할

#### 3.2 컨텍스트 주입 (`context_injector.py`)
```python
enriched_chunks = context_injector.inject_context(chunks)
# Output: [
#   {
#     "text": "Part 1 > Section 1.1\\n\\nSection 1.1 content...",
#     "original_text": "Section 1.1 content...",
#     "hierarchy": ["Part 1", "Section 1.1"]
#   }
# ]
```

#### 3.3 임베딩 생성 (`embedding_pipeline.py`)
```python
embedding_pipeline = EmbeddingPipeline(use_sparse=True)
embeddings = embedding_pipeline.embed_texts(texts)
# Output: {
#   "dense": [[0.1, 0.2, ...], ...],  # 1024차원 벡터
#   "sparse": [{"token_id": weight, ...}, ...]  # BM25 스타일
# }
```

#### 3.4 Dual Indexing (`dual_indexer.py`)
```python
dual_indexer = DualIndexer(collection_name="remon_regulations")
summary = dual_indexer.index(chunks, graph_data, source_file)
# Output: {
#   "status": "success",
#   "qdrant_chunks": 150,
#   "graph_nodes": 45,
#   "graph_edges": 78
# }
```

---

### 4. Phase 3: Graph Building (Optional)

**목적**: 엔티티 추출 → 관계 추론 → NetworkX 그래프 구축

#### 4.1 엔티티 추출 (`entity_extractor.py`)
```python
entity_extractor = EntityExtractor()
graph_data = entity_extractor.extract_from_pages(page_structures)
# Output: {
#   "nodes": [
#     {"id": "FDA", "type": "Organization", "context": "regulatory body"},
#     {"id": "Nicotine_Limit", "type": "Regulation"}
#   ],
#   "edges": [
#     {"source": "FDA", "target": "Nicotine_Limit", "relation": "enforces"}
#   ]
# }
```

#### 4.2 그래프 관리 (`graph_manager.py`)
```python
graph_manager = GraphManager()
graph_manager.build_graph(graph_data)
# NetworkX DiGraph 생성
# - 노드: 엔티티 (Organization, Regulation, Chemical 등)
# - 엣지: 관계 (enforces, regulates, contains 등)
```

---

## 주요 모듈 상세

### 1. `config.py` - 설정 관리

```python
class PreprocessConfig:
    # Vision Pipeline
    VISION_MODEL_COMPLEX = "gpt-4o"
    VISION_MODEL_SIMPLE = "gpt-4o-mini"  # ← 실제 OpenAI 모델명
    COMPLEXITY_THRESHOLD = 0.3
    VISION_DPI = 300
    
    # Embedding
    EMBEDDING_MODEL = "BAAI/bge-m3"
    EMBEDDING_DIMENSION = 1024
    
    # Qdrant (Docker + 로컬 이중 저장)
    QDRANT_HOST = "localhost"
    QDRANT_PORT = 6333
    QDRANT_PATH = "./data/qdrant"
    QDRANT_COLLECTION = "remon_regulations"
    
    # LangSmith
    ENABLE_LANGSMITH = True
    LANGCHAIN_PROJECT = "remon-vision-pipeline"
    
    @classmethod
    def setup_langsmith(cls):
        """LangSmith 환경변수 설정 (vision_orchestrator 초기화 시 호출)"""
        if cls.ENABLE_LANGSMITH and cls.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = cls.LANGCHAIN_API_KEY
```

### 2. `vision_orchestrator.py` - 전체 조율

```python
class VisionOrchestrator:
    def __init__(self):
        # LangSmith 초기화
        PreprocessConfig.setup_langsmith()
        
        # 컴포넌트 초기화
        self.renderer = PDFRenderer(dpi=300)
        self.complexity_analyzer = ComplexityAnalyzer()
        self.vision_router = VisionRouter(...)
        # ...
    
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        # Phase 1: Vision Ingestion
        vision_results = self._phase1_vision_ingestion(pdf_path)
        
        # Phase 2: Semantic Processing
        processing_results = self._phase2_semantic_processing(vision_results)
        
        # Phase 3: Graph Building (선택적)
        if self.enable_graph:
            graph_data = self._phase3_graph_building(vision_results)
        
        # Phase 4: Dual Indexing
        index_summary = self._phase4_dual_indexing(chunks, graph_data)
        
        return {
            "status": "success",
            "vision_extraction_result": vision_results,
            "graph_data": graph_data,
            "dual_index_summary": index_summary
        }
```

### 3. `__init__.py` - LangGraph 통합

```python
async def preprocess_node(state: AppState) -> AppState:
    request = state.get("preprocess_request")
    use_vision = request.get("use_vision_pipeline", False)
    
    if use_vision:
        # Vision Pipeline 실행
        result = await _run_vision_orchestrator(pdf_path)
        
        # State 업데이트
        state["vision_extraction_result"] = result["vision_extraction_result"]
        state["graph_data"] = result["graph_data"]
        state["dual_index_summary"] = result["dual_index_summary"]
    else:
        # 기존 파이프라인 실행
        result = await _run_orchestrator(pdf_path)
    
    return state
```

---

## KTNG 내부 데이터 처리

### 개요
KTNG 내부 대응 데이터(규제-제품-전략 쌍)를 별도 컬렉션에 저장하는 특수 파이프라인입니다.

### 디렉토리: `ktng_internal/`

```
ktng_internal/
├── ktng_pdf_parser.py           # PDF → JSON 케이스 추출
├── ktng_chunking_strategy.py    # 규제+제품 결합 청킹
└── ktng_embedding_processor.py  # 별도 컬렉션 저장
```

### 처리 흐름

```python
# 1. PDF 파싱
parser = KTNGPDFParser()
case_data_list = parser.parse_pdf("제품-규제 (KTNG 내부대응 data).pdf")
# Output: [
#   {
#     "case_id": "S001",
#     "regulation_text": "Nicotine concentration must not exceed 20mg/mL.",
#     "strategy": "니코틴 원액 투입 비율을 18mg/mL 수준으로 조정...",
#     "products": ["VapeX Mint 20mg", "TobaccoPure Classic 20mg"],
#     "country": "US"
#   }
# ]

# 2. 결합 청킹 (regulation_text + products만 임베딩)
chunker = RegulationProductChunking(max_chunk_size=512)
combined_chunks = chunker.create_combined_chunks(case_data_list)
# Output: [
#   {
#     "text": "Regulation: Nicotine concentration...\\nProducts: VapeX Mint 20mg, ...",
#     "metadata": {
#       "meta_case_id": "S001",
#       "meta_products": ["VapeX Mint 20mg", ...],
#       "meta_regulation_text": "...",
#       "meta_strategy": "...",  # 메타데이터로만 저장
#       "meta_country": "US"
#     }
#   }
# ]

# 3. 임베딩 및 별도 컬렉션 저장
processor = KTNGEmbeddingProcessor(
    collection_name="remon_internal_ktng",
    reset_collection=False
)
result = await processor.process_and_store(combined_chunks, source_file)
# Output: {
#   "status": "success",
#   "collection_name": "remon_internal_ktng",
#   "storage_mode": "dual (Docker + Local)",
#   "processed_chunks": 5
# }
```

### 특징
- **별도 컬렉션**: `remon_internal_ktng` (일반 규제와 분리)
- **이중 저장**: Docker Qdrant + 로컬 Qdrant 동시 저장
- **메타데이터 보존**: strategy는 임베딩하지 않고 메타데이터로만 저장
- **중복 방지**: 파일 해시 기반 중복 처리 방지

---

## 데이터 흐름

### Input → Output 변환 과정

```
┌─────────────────────────────────────────────────────────────┐
│ Input: PDF 파일                                             │
│ /path/to/regulation.pdf (50 pages)                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1 Output: Vision 추출 결과                            │
│ - 50개 페이지별 Markdown                                    │
│ - 모델 사용: GPT-4o (15페이지), GPT-4o-mini (35페이지)     │
│ - 총 토큰: 125,000                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2 Output: 청킹 결과                                   │
│ - 총 청크: 350개                                            │
│ - 평균 토큰: 512                                            │
│ - 계층 정보: Part > Section > Subsection                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3 Output: 그래프 데이터                               │
│ - 노드: 120개 (Organization, Regulation, Chemical)         │
│ - 엣지: 250개 (enforces, regulates, contains)              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Final Output: Qdrant + Graph                                │
│ - Qdrant: 350개 청크 (Dense + Sparse 벡터)                 │
│   - Docker: http://localhost:6333                           │
│   - 로컬: /home/minje/remon/data/qdrant                     │
│ - NetworkX: 120 노드, 250 엣지                              │
│ - 검색 가능: 하이브리드 (의미 + 키워드 + 그래프)           │
└─────────────────────────────────────────────────────────────┘
```

### AppState 필드

```python
class AppState(TypedDict, total=False):
    # 기존 필드
    preprocess_request: PreprocessRequest
    preprocess_results: List[Dict]
    preprocess_summary: PreprocessSummary
    
    # Vision Pipeline 추가 필드
    vision_extraction_result: List[Dict]  # 페이지별 Vision 추출
    graph_data: Dict[str, Any]            # 지식 그래프
    dual_index_summary: Dict[str, Any]    # Qdrant + Graph 요약
```

---

## 실행 방법

### 1. 환경 설정

`.env` 파일:
```bash
OPENAI_API_KEY=sk-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=remon-vision-pipeline

# Qdrant 설정
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_PATH=./data/qdrant
QDRANT_COLLECTION=remon_regulations
```

### 2. 의존성 설치

```bash
cd /home/minje/remon
uv pip install -e .
```

### 3. Qdrant 시작

```bash
# Docker Qdrant 시작
bash scripts/start_qdrant.sh

# 확인
curl http://localhost:6333/collections
```

### 4. Python 코드에서 실행

```python
from app.ai_pipeline.preprocess import preprocess_node

# Vision Pipeline 실행
state = {
    "preprocess_request": {
        "pdf_paths": ["/path/to/regulation.pdf"],
        "use_vision_pipeline": True
    }
}

result = await preprocess_node(state)

# 결과 확인
print(result["vision_extraction_result"])
print(result["graph_data"])
print(result["dual_index_summary"])
```

### 5. KTNG 내부 데이터 처리

```python
from app.ai_pipeline.preprocess.ktng_internal import (
    KTNGPDFParser,
    RegulationProductChunking,
    KTNGEmbeddingProcessor
)

# 파싱
parser = KTNGPDFParser()
case_data = parser.parse_pdf("제품-규제 (KTNG 내부대응 data).pdf")

# 청킹
chunker = RegulationProductChunking()
chunks = chunker.create_combined_chunks(case_data)

# 저장
processor = KTNGEmbeddingProcessor(
    collection_name="remon_internal_ktng",
    reset_collection=False
)
result = await processor.process_and_store(chunks, source_file)
```

---

## 비용 분석

### 예상 비용 (100페이지 문서)

| 시나리오 | GPT-4o | GPT-4o-mini | 총 비용 |
|---------|--------|-------------|------------|
| 표 없는 문서 | 0% | 100% | ~$1.50 |
| 표 많은 문서 | 60% | 40% | ~$15.00 |
| 혼합 문서 | 30% | 70% | ~$8.00 |

**비용 절감 전략**:
- `COMPLEXITY_THRESHOLD` 조정 (기본 0.3 → 0.5로 높이면 GPT-4o 사용 감소)
- `VISION_DPI` 낮추기 (300 → 150)
- 그래프 비활성화 (`ENABLE_GRAPH_EXTRACTION=false`)

---

## 트러블슈팅

### 1. pypdfium2 설치 실패
```bash
uv pip install pypdfium2
```

### 2. LangSmith 연결 실패
`.env`에서 `LANGCHAIN_API_KEY` 확인

### 3. Qdrant 연결 실패
```bash
# Docker Qdrant 시작
bash scripts/start_qdrant.sh

# 로그 확인
docker logs qdrant
```

### 4. 메모리 부족
- DPI 낮추기: `VISION_DPI=150`
- 배치 크기 줄이기: `EMBEDDING_BATCH_SIZE=16`

### 5. 이중 저장 실패
```python
# 로컬 Qdrant 경로 확인
ls -la /home/minje/remon/data/qdrant

# Docker Qdrant 확인
curl http://localhost:6333/collections
```

---

## 다음 단계

1. **Neo4j 연동**: NetworkX → Neo4j 마이그레이션
2. **GraphEval 패턴**: 지식 그래프 검증 Agent 추가
3. **Batch Processing**: 여러 PDF 병렬 처리
4. **캐싱**: 동일 문서 재처리 방지
5. **OpenSearch 통합**: 하이브리드 검색 강화
6. **출력 저장**: LLM 출력을 파일로 저장하는 기능 추가

---

**문서 버전**: 1.1  
**최종 업데이트**: 2025-01-14  
**이전 버전**: [VISION_PIPELINE_ARCHITECTURE_v1.0.md](.github/VISION_PIPELINE_ARCHITECTURE_v1.0.md)
