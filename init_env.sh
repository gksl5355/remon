#!/usr/bin/env bash
set -e

echo "🚀 REMON 개발 환경 초기화 시작..."

# 1️⃣ OS별 확인
if ! command -v curl &> /dev/null; then
    echo "❌ curl이 필요합니다. 설치 후 다시 실행해주세요."
    exit 1
fi

# 2️⃣ uv 설치 여부 확인
if ! command -v uv &> /dev/null; then
    echo "🧩 uv가 설치되어 있지 않습니다. 설치를 진행합니다..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✅ uv가 이미 설치되어 있습니다: $(uv --version)"
fi

# 3️⃣ Python 버전 확인
PY_VER=$(python3 -V 2>&1)
echo "🐍 Python 버전 확인: $PY_VER"

# 4️⃣ pyproject.toml 존재 확인
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml 파일을 찾을 수 없습니다. remon 루트에서 실행해주세요."
    exit 1
fi

# 5️⃣ uv 환경 동기화
read -p "⚙️  설치할 모드 선택 [1: 기본(FastAPI) / 2: AI / 3: Crawler]: " MODE

case $MODE in
    1)
        echo "🔧 FastAPI 기본 환경 설치 중..."
        uv sync
        ;;
    2)
        echo "🧠 AI 환경 설치 중 (LangChain + Torch)..."
        uv sync --extra ai
        ;;
    3)
        echo "🌍 Crawler 환경 설치 중..."
        uv sync --extra crawler
        ;;
    *)
        echo "⚠️ 잘못된 선택입니다. 기본 환경(FastAPI)으로 진행합니다."
        uv sync
        ;;
esac

# 6️⃣ .env 파일 생성 (없는 경우)
if [ ! -f ".env" ]; then
cat <<EOF > .env
# 기본 환경 설정
APP_ENV=dev
DB_URL=sqlite:///./data/remon.db
REDIS_URL=redis://localhost:6379
EOF
    echo "✅ .env 파일 생성 완료"
fi

# 7️⃣ FastAPI 서버 실행 안내
echo ""
echo "✅ 패키지 설치 완료!"
echo "서버를 실행하려면 아래 명령어를 입력하세요:"
echo ""
echo "   uv run uvicorn app.main:app --reload"
echo ""

