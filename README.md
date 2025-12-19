REMON

AI-Native Regulation Monitoring & Mapping System

REMON은 글로벌 규제 문서를 자동으로 수집·분석하고,
제품 단위 영향도 평가와 대응 리포트를 생성하는 AI 기반 규제 대응 플랫폼입니다.

규제 변경 감지부터 판단 통제(Human-in-the-Loop)까지,
실무 규제 대응 흐름 전체를 하나의 파이프라인으로 통합합니다.

Overview

글로벌 규제를 다루는 기업은 국가·기관별로 상이한 규제 구조와 잦은 개정,
그리고 미탐·오탐에 따른 높은 리스크를 동시에 관리해야 합니다.

REMON은 규제 문서를 구조적으로 분해하고,
제품 데이터와 연결하여 판단 가능한 형태의 규제 정보로 전환합니다.

Problem

국가·기관별로 상이한 규제 문서 형식(PDF, HTML, 공지 등)
규제 변경 여부 판단의 사람 의존성
단순 키워드 기반 검토로 인한 미탐 / 오탐 발생
제품·성분·패키지 단위 영향도 분석의 비효율
규제 대응 판단 근거에 대한 추적 어려움

Solution

REMON은 다음 과정을 자동화합니다.

규제 문서 수집 및 변경 감지
규제 문서의 구조적 분해
제품 데이터와의 정합적 매핑
AI 기반 영향도 분석 및 대응 전략 생성
Human-in-the-Loop를 통한 판단 통제

이를 통해 규제 대응을 빠르게, 그리고 통제 가능한 방식으로 수행할 수 있습니다.

Key Features

Regulation Change Detection
이전 버전 대비 의미 기반 규제 변경 감지

Structural Regulation Parsing
국가별 상위 규제 체계에 기반한 문서 구조화

Hybrid Search (Dense + Sparse)
의미 검색과 키워드 정합을 결합한 규제 검색

Product-Level Impact Mapping
제품 성분·패키지·라벨 단위 영향도 분석

Human-in-the-Loop Validation
AI 판단 결과에 대한 승인·수정·보류 통제

Automated Report Generation
변경 요약, 영향 제품, 대응 전략 리포트 자동 생성

System Architecture

REMON은 규제 수집, 전처리, AI 분석, 리포트 생성으로 이어지는
End-to-End 파이프라인 구조로 설계되었습니다.

아키텍처 다이어그램과 상세 설명은 문서에서 관리합니다.
docs/architecture.md

Tech Stack

Backend / AI
Python 3.11
FastAPI
LangGraph (Multi-Agent Workflow)
LLM 기반 분석

Data
PostgreSQL (Metadata, JSONB)
Qdrant (Vector Database)
Dense + Sparse Hybrid Embedding

Frontend
Vue 3
Tailwind CSS

Infra
Docker
Kubernetes
GitHub Actions

Project Structure
.
├─ backend/
├─ frontend/
├─ database/
├─ infra/
└─ docs/

Workflow (High-Level)
1. Regulation Ingestion
2. Preprocessing & Structuring
3. Change Detection
4. Product Mapping
5. HITL Validation
6. Report Generation

Documentation

세부 설계, 알고리즘, 판단 로직은 README에서 분리하여 관리합니다.

Architecture Overview
docs/architecture.md

AI Workflow & Agents
docs/ai-workflow.md

Data Model & ERD
docs/data-model.md

HITL Design & Validation Flow
docs/hitl.md

Roadmap

국가별 규제 소스 확장
규제 도메인 확장 (제약, 화장품, ESG 등)
리포트 템플릿 고도화
규제 대응 이력 기반 분석 기능 추가

Team Members
<table> <tr> <td align="center"> <img src="https://avatars.githubusercontent.com/SunYoung710" width="120" style="border-radius: 50%;" alt="박선영"/><br/> <b>박선영</b><br/> <sub>Frontend Engineer</sub><br/> <sub>UI/UX · Report Viewer · API Integration</sub><br/> <a href="https://github.com/SunYoung710">@SunYoung710</a> </td> <td align="center"> <img src="https://avatars.githubusercontent.com/bofoto" width="120" style="border-radius: 50%;" alt="조영우"/><br/> <b>조영우</b><br/> <sub>Backend Lead</sub><br/> <sub>API Gateway · Transaction · Service Orchestration</sub><br/> <a href="https://github.com/bofoto">@bofoto</a> </td> <td align="center"> <img src="https://avatars.githubusercontent.com/Nam707" width="120" style="border-radius: 50%;" alt="남지수"/><br/> <b>남지수</b><br/> <sub>Database Engineer</sub><br/> <sub>PostgreSQL Schema · ORM · Repository Layer</sub><br/> <a href="https://github.com/Nam707">@Nam707</a> </td> </tr> <tr> <td align="center"> <img src="https://avatars.githubusercontent.com/bluepaled0t" width="120" style="border-radius: 50%;" alt="고서아"/><br/> <b>고서아</b><br/> <sub>AI Pipeline Engineer</sub><br/> <sub>LangGraph Workflow · Strategy / Report Generator</sub><br/> <a href="https://github.com/bluepaled0t">@bluepaled0t</a> </td> <td align="center"> <img src="https://avatars.githubusercontent.com/gksl5355" width="120" style="border-radius: 50%;" alt="조태환"/><br/> <b>조태환</b><br/> <sub>RAG Engineer</sub><br/> <sub>Embedding · Qdrant · Retrieval Pipeline</sub><br/> <a href="https://github.com/gksl5355">@gksl5355</a> </td> <td align="center"> <img src="./docs/andong.jpg" width="120" style="border-radius: 50%;" alt="김민제"/><br/> <b>김민제</b><br/> <sub>Data / Collect Engineer</sub><br/> <sub>Crawling · Preprocessing · Collect / Refine Pipelines</sub><br/> <a href="https://github.com/dreamFORcreative">@dreamFORcreative</a> </td> </tr> </table>
License & Third-Party Notices

This project is intended for educational and portfolio purposes.
Commercial use requires separate permission.

This project uses the following open-source libraries:

Apache License 2.0
fastapi, uvicorn, torch, langchain, pandas

MIT License
aiohttp, loguru, python-dotenv

BSD License
numpy

Detailed license texts are available in each respective repository.
