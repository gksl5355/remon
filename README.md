# REMON – Regulation Monitoring AI System

AI 기반 해외 규제 문서를 자동 수집·정제·분석·매핑하여 제품 영향도와 대응 전략을 생성하는 규제 분석 자동화 플랫폼.

PDF/HTML 규제 문서를 업로드하면 **번역 → 임베딩 → 매핑 → 영향도 → 리포트**까지 단일 파이프라인에서 처리한다.

---

## 1. Overview

REMON은 국가별 규제 문서를 자동으로 처리해
기업의 제품별 영향도 분석과 대응 전략 도출 과정을 단축하는 것을 목표로 한다.

**Pipeline:**
규제 업로드 → 텍스트 추출/전처리 → 번역 → 임베딩 → 제품 매핑 → 영향도 분석 → 리포트 생성

---

## 2. Features

* 규제 PDF/HTML 파일 업로드
* 텍스트 추출 및 언어 감지/번역
* 문서 청킹 및 BGE-M3 임베딩 생성
* 제품–규제 매핑 및 영향도 산출
* 리포트 요약 및 전략 생성(GPT-4o mini 기반)
* 임베딩 검색(Qdrant), Text 검색(OpenSearch 예정)
* 리포트 다운로드

---

## 3. System Architecture

<img src="./docs/ai.jpg" style="width:100px;">
<img src="./docs/the-clean-architecture.png" style="width:100px;">

**Backend(FastAPI)**

* CollectService: 규제 파일 수집 및 메타데이터
* RefineService: 추출/번역/임베딩
* MappingService: 제품 매핑 및 영향도 계산
* ReportService: 전략·요약 리포트 생성
* AI Pipeline: LangGraph 기반 LLM workflow

**Storages**

* PostgreSQL: 문서/제품/메타데이터
* Qdrant: 벡터 임베딩
* OpenSearch: Hybrid Retrieval (예정)
* Redis: 캐시·상태·비동기 처리 옵션

---

## 4. Tech Stack

**Backend**

* FastAPI · Python 3.11 · uv
* SQLAlchemy · Pydantic
* Springboot

**AI Pipeline**

* GPT-4o mini, GPT-5 mini
* BGE-M3 Embedding
* LangGraph

**Databases**

* PostgreSQL
* Qdrant

**Frontend**

* Vue 3 · Vite
* TailwindCSS

**Infra**

* Docker
* Amazon EKS
* S3

---

## 5. Getting Started

### 5.1 Prerequisites

* Python 3.11
* uv
* Docker(optional)
* Node.js 20+(Frontend)

---

### 5.2 Setup Environment

```bash
chmod +x init_env.sh
./init_env.sh
```

해당 스크립트는 다음을 자동 처리한다.

* uv 설치
* Python 패키지 설치
* .env 생성
* VSCode 개발환경 설정

---

### 5.3 Run Backend

```bash
uv run uvicorn app.main:app --reload
```

---

### 5.4 Run Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 6. Project Structure

```
/app
  ├── api/                 # API 라우팅
  ├── services/            # Collect / Refine / Mapping / Report 서비스
  ├── ai_pipeline/         # LangGraph 기반 LLM 파이프라인
  ├── vectorstore/         # Qdrant 연동
  ├── core/                # DB 설정, ORM, Repository
  ├── config/              # 환경 설정
  ├── main.py

/frontend
  ├── pages/
  ├── components/
  ├── services/
```

---

## 7. API Documentation

* Swagger UI: **`http://localhost:8000/docs`**
* ReDoc: **`http://localhost:8000/redoc`**

---

## 8. Documents

세부 설계 문서는 `/docs` 폴더에 정리됨.

* `/docs/architecture/*` – 시스템 아키텍처
* `/docs/database/ERD_REMON.png` – ERD
* `/docs/pipeline/*` – 파이프라인 상세
* `/docs/specs/*` – 모듈/데이터 구조 명세

---

## 9. Team Members

<table>
  <tr>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/SunYoung710" width="120" style="border-radius: 50%;" alt="박선영"/><br/>
      <b>박선영</b><br/>
      <sub>Frontend Engineer</sub><br/>
      <sub>UI/UX · Report Viewer · API 연동</sub><br/>
      <a href="https://github.com/SunYoung710">@SunYoung710</a>
    </td>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/bofoto" width="120" style="border-radius: 50%;" alt="조영우"/><br/>
      <b>조영우</b><br/>
      <sub>Backend Lead</sub><br/>
      <sub>API Gateway · Transaction · Service Orchestration</sub><br/>
      <a href="https://github.com/bofoto">@bofoto</a>
    </td>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/Nam707" width="120" style="border-radius: 50%;" alt="남지수"/><br/>
      <b>남지수</b><br/>
      <sub>Database Engineer</sub><br/>
      <sub>PostgreSQL Schema · ORM · Repository Layer</sub><br/>
      <a href="https://github.com/Nam707">@Nam707</a>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/bluepaled0t" width="120" style="border-radius: 50%;" alt="고서아"/><br/>
      <b>고서아</b><br/>
      <sub>AI Pipeline Engineer</sub><br/>
      <sub>LangGraph Workflow · Strategy/Report Generator</sub><br/>
      <a href="https://github.com/bluepaled0t">@bluepaled0t</a>
    </td>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/gksl5355" width="120" style="border-radius: 50%;" alt="조태환"/><br/>
      <b>조태환</b><br/>
      <sub>RAG Engineer</sub><br/>
      <sub>Embedding · Qdrant · Retrieval Pipeline</sub><br/>
      <a href="https://github.com/gksl5355">@gksl5355</a>
    </td>
    <td align="center">
      <img src="https://avatars.githubusercontent.com/dreamFORcreative" width="120" style="border-radius: 50%;" alt="김민제"/><br/>
      <b>김민제</b><br/>
      <sub>Data/Collect Engineer</sub><br/>
      <sub>Crawling · Preprocessing · Collect/Refine Pipelines</sub><br/>
      <a href="https://github.com/dreamFORcreative">@dreamFORcreative</a>
    </td>
  </tr>
</table>

---

## 10. License



---

## 11. Contact



---







