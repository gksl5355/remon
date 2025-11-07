#!/usr/bin/env bash
set -e

echo "🚀 REMON 개발 환경 초기화 시작..."

# ------------------------------
# OS 모드 판별
# ------------------------------
MODE="$1"
if [[ "$MODE" == "-mac" ]]; then
    OS_MODE="mac"
    echo "💻 macOS 모드로 실행합니다. (Homebrew 사용)"
else
    OS_MODE="linux"
    echo "🐧 Linux/WSL 모드로 실행합니다. (curl + install.sh 사용)"
fi

# ------------------------------
# 1️⃣ uv 설치 확인
# ------------------------------
if ! command -v uv &> /dev/null; then
    echo "🧩 uv가 설치되어 있지 않습니다. 설치를 진행합니다..."

    if [[ "$OS_MODE" == "mac" ]]; then
        # macOS: Homebrew 사용
        if command -v brew &> /dev/null; then
            echo "🍺 Homebrew로 uv 설치 중..."
            brew install uv
        else
            echo "❌ Homebrew가 설치되어 있지 않습니다."
            echo "   아래 명령어로 먼저 설치한 후 다시 실행해주세요:"
            echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            exit 1
        fi
    else
        # Linux/WSL: curl + install.sh 사용
        if ! command -v curl &> /dev/null; then
            echo "📦 curl이 필요합니다. 설치 중..."
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y curl
            elif command -v yum &> /dev/null; then
                sudo yum install -y curl
            else
                echo "❌ curl 설치를 자동으로 처리할 수 없습니다. 수동으로 설치해주세요."
                exit 1
            fi
        fi

        echo "⬇️ uv 설치 스크립트 실행 중..."
        curl -LsSf https://astral.sh/uv/install.sh | sh

        export PATH="$HOME/.local/bin:$PATH"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc 2>/dev/null || true
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc 2>/dev/null || true
    fi

    # 설치 확인
    if ! command -v uv &> /dev/null; then
        echo "⚠️ uv 명령어가 아직 인식되지 않습니다."
        echo "   새 터미널을 열거나 아래 명령 중 하나를 실행해주세요:"
        echo "   source ~/.bashrc  또는  source ~/.zshrc"
        exit 1
    fi
else
    echo "✅ uv가 이미 설치되어 있습니다: $(uv --version)"
fi

# ------------------------------
# 2️⃣ Python 버전 확인
# ------------------------------
PY_VER=$(python3 -V 2>&1 || true)
if [[ -z "$PY_VER" ]]; then
    echo "❌ Python3가 설치되어 있지 않습니다."
    echo "   macOS: brew install python"
    echo "   Ubuntu: sudo apt install python3"
    exit 1
fi
echo "🐍 Python 버전 확인: $PY_VER"

# ------------------------------
# 3️⃣ pyproject.toml 확인
# ------------------------------
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml 파일을 찾을 수 없습니다. remon 루트에서 실행해주세요."
    exit 1
fi

# ------------------------------
# 4️⃣ 환경 선택
# ------------------------------
read -p "⚙️ 설치할 모드 선택 [1: 기본(FastAPI) / 2: AI / 3: Crawler]: " ENV_MODE

case $ENV_MODE in
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

# ------------------------------
# 5️⃣ .env 파일 자동 생성
# ------------------------------
if [ ! -f ".env" ]; then
cat <<EOF > .env
# 기본 환경 설정
APP_ENV=dev
DB_URL=sqlite:///./data/remon.db
REDIS_URL=redis://localhost:6379
EOF
    echo "✅ .env 파일 생성 완료"
fi

# ------------------------------
# 6️⃣ 완료 안내
# ------------------------------
echo ""
echo "✅ 모든 설정이 완료되었습니다!"
echo "서버 실행 명령:"
echo ""
echo "   uv run uvicorn app.main:app --reload"
echo ""

