프로젝트 개요
# REMON Project Context
## 1. 프로젝트 개요
**프로젝트명:** REMON (Regulation Monitoring & Mapping System)  
**목적:** 해외 규제 문서를 자동 수집·정제·분석하여 제품 영향도 및 대응 전략을 생성하는 AI 기반 규제 대응 자동화 플랫폼.  
**핵심 흐름:** 규제 수집 → 데이터 정제(번역/임베딩) → 매핑 및 영향도 평가 → 리포트 생성  
**주요 기술 스택**
- FastAPI (Backend, Python 3.11, uv 환경)
- Vue3 (Frontend)
- PostgreSQL (Main DB)
- Chroma (VectorDB)
- Redis (옵션: 캐시/세션/비동기 큐)
- OpenSearch (텍스트 검색, Hybrid Retrieval 예정)
- LLM: GPT-4o mini  
- Embedding Model: BGE-M3  
---
## 2. 시스템 아키텍처 요약
- 사용자(관리자)는 PDF/HTML 형식의 규제문서를 업로드 또는 분석 요청  
- FastAPI 백엔드가 데이터 수집부터 리포트 생성까지 전체 파이프라인 담당  
- 주요 내부 모듈:
  - **RefineService:** 번역 및 임베딩
  - **MappingService:** 규제-제품 매칭 및 영향도 평가
  - **ReportService:** 요약·전략 생성 및 다운로드  
- 데이터 저장 구조:
  - **SQL DB:** 규제·제품·리포트·메타데이터 저장  
  - **Chroma VectorDB:** 임베딩 벡터 및 메타 저장  
  - **OpenSearch:** 키워드/필터 검색 (검토 중)
  - **Redis:** 옵션 – 세션·캐시·상태 관리
- 현재 배포는 단일 FastAPI 기준, 추후 EKS에서 서비스 단위 확장 예정  
---
## 3. 개발 진행상황
| 항목 | 상태 | 비고 |
|------|------|------|
| FastAPI 기본환경 (uv) | ✅ 완료 | |
| ERD | ✅ 초안 완성 | 일부 조정 예정 |
| SQLAlchemy 모델화 | @지수 | |
| 더미데이터 생성 | ✅ 초안 완성 | @민제, @영우, @지수 검토중 |
| VectorDB 스키마 | @민제  검토중|  |
| OpenSearch 연계 | 🕐 검토 중 | Qdrant - dense+sparse 예정 |
| API 문서 자동화 | ✅| |
| 배포(EKS) | ⛔ 미정 | |
---
## 4. 모듈별 역할 요약
| 모듈 | 역할 |
|------|------|
| **CollectService** | 외부 규제문서 수집 및 메타데이터 저장 |
| **RefineService** | 텍스트 추출, 번역, 임베딩 생성 |
| **MappingService** | 제품-규제 매칭, 영향도 계산 |
| **ReportService** | 대응전략 및 요약 생성, 리포트 다운로드 |
| **API Layer** | REST API 요청 처리, 라우팅 |
| **Service Layer** | Collect / Refine / Mapping / Report orchestrator |
| **AI Pipeline Layer** | LangGraph 기반 LLM 호출, workflow 관리 |
| **Vector/Search Layer** | Chroma / OpenSearch 관리 계층 |
---
## 5. 팀 역할 분담
```
구분  인원  주요 폴더 / 파일  책임 범위
FE1 – 프론트엔드/UI 담당 박선영  /frontend/→ pages/, components/, composables/, services/api.js  사용자 인터페이스 / API 연동 / 리포트 시각화
BE1 – 백엔드 리드 (트랜잭션·API 게이트웨이) 조영우/app/api/
/app/services/
/app/config/
/app/main.py  전체 API 라우팅 / 트랜잭션 관리 / 서비스 orchestration
BE2 – 데이터베이스 엔지니어 (Repository & Schema) 남지수  /app/core/→ database.py, models/, schemas/, repositories/ DB 구조 설계 / Repository 표준화 / ORM
AI1 – LangGraph 파이프라인 엔지니어  고서아 /app/ai_pipeline/pipeline_orchestrator.py/app/ai_pipeline/chains//app/ai_pipeline/agents/ LLM 파이프라인 (LangGraph) 설계 / 대응전략·리포트 생성
AI2 – RAG 엔지니어 (임베딩·검색 시스템) 조태환 /app/ai_pipeline/memory//app/vectorstore//app/ai_pipeline/utils/  RAG 검색·임베딩·VectorDB 구축
DE1 – AI/DATA엔지니어 (수집·전처리 파이프라인)  김민제  /app/crawler//app/pipelines/collect//app/pipelines/refine//app/services/collect_service.py  규제 데이터 크롤링 / 전처리 / RAG 입력 데이터 생성
```
---
## 6. RAG Schema 개요 (초안)
| 구분 | 상태 | 내용 |
|------|------|------|
| 임베딩 모델 | ✅ BGE-M3 |
| LLM | ✅ GPT-4o mini |
| VectorDB | ✅ Chroma |
| OpenSearch | 🕐 Hybrid 실험 예정 |
| 국가 구분 방식 | ✅ meta_country 필드 기반 |
| 임베딩 저장 방식 | 🟡 VectorDB만 저장, SQL엔 문서 메타만 저장 권장 |
| 검색 로직 | 🕐 Hybrid Retrieval (Chroma + OpenSearch) 예정 |
| Redis | 🕐 캐시/세션 중심, 큐는 추후 확장 |
| LLM 호출 방식 | ✅ 현재는 직렬(순차), 추후 비동기(batch) 검토 |
**Vector 컬렉션 예시**
| 필드명 | 타입 | 설명 |
|---------|------|------|
| id | UUID | chunk 식별자 |
| text | string | 규제 문서 조항 텍스트 |
| embedding | list[float] | BGE-M3 임베딩 벡터 |
| meta_regulation_id | int | 규제 DB 참조 |
| meta_country | string | 국가 코드 |
| meta_lang | string | 언어 |
| meta_date | date | 시행일 |
| meta_source | string | 원문 파일 경로 또는 URL |
---
## 7. LLM 호출 정책
- **현재:** 순차 처리 (직렬)
- **이후:** 성능 병목 발생 시 Redis 기반 비동기 큐로 확장
- 병렬 호출은 FastAPI async + await 구조로 변환 예정  
- 번역 정확성 검증이 끝난 후에만 비동기 병렬화 적용  
---
## 8. 참고 자료
```
/docs/architecture/REMON_system_final.png  
/docs/architecture/system_architecture.png  
/docs/architecture/dataflow_mapping_report.png  
/docs/architecture/service_io_structure.png  
/docs/database/ERD_REMON.png
```


| 구분 | 담당자 | 책임 범위 |
|:---:|:---:|:---|
| **FE1 – 프론트엔드/UI 담당** | <img src="https://avatars.githubusercontent.com/SunYoung710" width=120px alt="박선영"/> [박선영](https://github.com/SunYoung710) | 사용자 인터페이스 / API 연동 / 리포트 시각화 |
| **BE1 – 백엔드 리드 (트랜잭션·API 게이트웨이)** | <img src="https://avatars.githubusercontent.com/dreamFORcreative" width=120px alt="조영우"/> [조영우](https://github.com/dreamFORcreative) | 전체 API 라우팅 / 트랜잭션 관리 / 서비스 orchestration |
| **BE2 – 데이터베이스 엔지니어 (Repository & Schema)** | <img src="https://avatars.githubusercontent.com/Nam707" width=120px alt="남지수"/> [남지수](https://github.com/Nam707) | DB 구조 설계 / Repository 표준화 / ORM |
| **AI1 – LangGraph 파이프라인 엔지니어** | <img src="https://avatars.githubusercontent.com/bluepaled0t" width=120px alt="고서아"/> [고서아](https://github.com/bluepaled0t) | LLM 파이프라인 (LangGraph) 설계 / 대응전략·리포트 생성 |
| **AI2 – RAG 엔지니어 (임베딩·검색 시스템)** | <img src="https://avatars.githubusercontent.com/gksl5355" width=120px alt="조태환"/> [조태환](https://github.com/gksl5355) | RAG 검색·임베딩·VectorDB 구축 |
| **DE1 – AI/DATA 엔지니어 (수집·전처리 파이프라인)** | <img src="https://avatars.githubusercontent.com/DWECK" width=120px alt="김민제"/> [김민제](https://github.com/DWECK) | 규제 데이터 크롤링 / 전처리 / RAG 입력 데이터 생성 |



# 🚀 Remon 프로젝트 실행 가이드

---

## 1️⃣ 저장소 클론
- 저장소를 클론하고 디렉토리로 이동합니다.
  ```bash
  git clone https://github.com/gksl5355/remon.git
  cd remon


---

## 2️⃣ 환경 초기화

* 아래 스크립트를 실행하면 다음이 자동으로 설정됩니다:

  * uv 설치
  * 의존성 패키지 설치
  * .env 환경변수 세팅
  * VSCode 환경 설정

  ```bash
  chmod +x init_env.sh
  ./init_env.sh


---

## 3️⃣ 서버 실행

* FastAPI 서버를 실행합니다.

  ```bash
  uv run uvicorn app.main:app --reload


---






