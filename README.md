# 1️⃣ Git clone
git clone https://github.com/gksl5355/remon.git
cd remon

# 2️⃣ init 실행
chmod +x init_env.sh
./init_env.sh
# → uv 자동 설치 + 의존성 설치 + .env 세팅 + VSCode 세팅

# 3️⃣ 서버 실행
uv run uvicorn app.main:app --reload
