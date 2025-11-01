#!/bin/bash
# ==========================================
# REMON Project 폴더 구조 정리 스크립트
# api → backend
# ai → ai-engine
# web → frontend
# docker-compose.yml 자동 업데이트
# ==========================================

echo "🔄 REMON 프로젝트 폴더 리네이밍 시작..."

# 1. 폴더 이름 변경
if [ -d "api" ]; then
  git mv api backend
  echo "✅ api → backend 변경 완료"
fi

if [ -d "ai" ]; then
  git mv ai ai-engine
  echo "✅ ai → ai-engine 변경 완료"
fi

if [ -d "web" ]; then
  git mv web frontend
  echo "✅ web → frontend 변경 완료"
fi

# 2. docker-compose.yml 업데이트
if [ -f "docker-compose.yml" ]; then
  echo "⚙️ docker-compose.yml 수정 중..."

  # sed 명령으로 서비스명, 경로, 포트 라벨 수정
  sed -i.bak \
    -e 's|api/|backend/|g' \
    -e 's|ai/|ai-engine/|g' \
    -e 's|web/|frontend/|g' \
    -e 's|api:|backend:|' \
    -e 's|ai:|ai-engine:|' \
    -e 's|web:|frontend:|' \
    docker-compose.yml

  echo "✅ docker-compose.yml 경로 및 서비스명 갱신 완료"
else
  echo "⚠️ docker-compose.yml 파일이 없습니다. 새로 생성합니다."

  cat <<EOF > docker-compose.yml
version: "3"
services:
  backend:
    build: ./backend
    container_name: remon_backend
    ports:
      - "8080:8080"
    networks:
      - remon-net

  ai-engine:
    build: ./ai-engine
    container_name: remon_ai
    ports:
      - "5000:5000"
    networks:
      - remon-net

  frontend:
    build: ./frontend
    container_name: remon_frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE=http://localhost:8080
      - VITE_AI_BASE=http://localhost:5000
    networks:
      - remon-net

networks:
  remon-net:
    driver: bridge
EOF
  echo "✅ docker-compose.yml 새로 생성 완료"
fi

# 3. 커밋
git add .
git commit -m "chore: rename folders (api→backend, ai→ai-engine, web→frontend) and update docker-compose.yml"

echo "🎉 리네이밍 및 설정 수정 완료!"


