#!/usr/bin/bash
set -e

echo "🐍 Python 3.11.13 환경 자동 세팅 시작..."

# ------------------------------
# OS 판별
# ------------------------------
OS_TYPE="$(uname -s)"
if [[ "$OS_TYPE" == "Darwin" ]]; then
    OS_MODE="mac"
    echo "💻 macOS 환경 감지됨 (Homebrew 사용)"
else
    OS_MODE="linux"
    echo "🐧 Linux/WSL 환경 감지됨 (apt 사용)"
fi

# ------------------------------
# 1️⃣ pyenv 설치 여부 확인
# ------------------------------
if ! command -v pyenv &> /dev/null; then
    echo "🧩 pyenv가 설치되어 있지 않습니다. 설치를 진행합니다..."

    if [[ "$OS_MODE" == "mac" ]]; then
        if ! command -v brew &> /dev/null; then
            echo "❌ Homebrew가 설치되어 있지 않습니다. 먼저 아래 명령을 실행해주세요:"
            echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            exit 1
        fi
        brew install pyenv
    else
        # Linux / WSL
        echo "📦 필수 빌드 종속성 설치 중..."
        sudo apt update
        sudo apt install -y build-essential libssl-dev zlib1g-dev \
            libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
            libncurses5-dev libncursesw5-dev xz-utils tk-dev git \
            libffi-dev liblzma-dev
        echo "⬇️ pyenv 설치 중..."
        curl https://pyenv.run | bash
    fi
else
    echo "✅ pyenv가 이미 설치되어 있습니다: $(pyenv --version)"
fi

# ------------------------------
# 2️⃣ pyenv PATH 세팅
# ------------------------------
if [[ "$OS_MODE" == "mac" ]]; then
    RC_FILE="$HOME/.zshrc"
else
    RC_FILE="$HOME/.bashrc"
fi

if ! grep -q 'pyenv init' "$RC_FILE" 2>/dev/null; then
    echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> "$RC_FILE"
    echo 'eval "$(pyenv init -)"' >> "$RC_FILE"
    echo "✅ pyenv 초기화 설정이 $RC_FILE 에 추가되었습니다."
fi

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"

# ------------------------------
# 3️⃣ Python 3.11.13 설치
# ------------------------------
if ! pyenv versions --bare | grep -q '^3.11.13$'; then
    echo "⬇️ Python 3.11.13 설치 중..."
    pyenv install 3.11.13
else
    echo "✅ Python 3.11.13 이미 설치됨"
fi

# ------------------------------
# 4️⃣ 글로벌 버전 설정
# ------------------------------
pyenv global 3.11.13
pyenv rehash

# ------------------------------
# 5️⃣ 확인
# ------------------------------
echo ""
echo "🐍 Python 버전 확인:"
python -V

PY_PATH=$(which python)
echo "📂 Python 실행 경로: $PY_PATH"

echo ""
echo "✅ pyenv 및 Python 3.11.13 글로벌 세팅 완료!"
echo "다음 명령으로 설정이 즉시 반영되지 않으면 아래를 실행하세요:"
echo ""
echo "   source $RC_FILE"
echo ""

# ------------------------------
# 6️⃣ uv 설치 (Python 패키지 관리자)
# ------------------------------
if ! command -v uv &> /dev/null; then
    echo "📦 uv 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "✅ uv 설치 완료"
else
    echo "✅ uv가 이미 설치되어 있습니다: $(uv --version)"
fi

# ------------------------------
# 7️⃣ 가상환경 생성 및 의존성 설치
# ------------------------------
if [ -d ".venv" ]; then
    echo "🔄 기존 가상환경 제거 중..."
    rm -rf .venv
fi

echo "🔧 가상환경 생성 중..."
uv venv

echo "📦 의존성 설치 중..."
source .venv/bin/activate
uv pip install -e .

echo ""
echo "✅ 전체 설정 완료!"
echo ""
echo "가상환경 활성화:"
echo "   source .venv/bin/activate"
echo ""

