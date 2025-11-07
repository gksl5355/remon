
# 🚀 Remon 프로젝트 실행 가이드

---

## 1️⃣ 저장소 클론
- 저장소를 클론하고 디렉토리로 이동합니다.
  ```bash
  git clone https://github.com/gksl5355/remon.git
  cd remon
````

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
  ````

---

## 3️⃣ 서버 실행

* FastAPI 서버를 실행합니다.

  ```bash
  uv run uvicorn app.main:app --reload
  ```

---

