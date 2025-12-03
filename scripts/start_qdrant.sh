#!/bin/bash
# Qdrant 도커 컨테이너 실행

echo "🚀 Qdrant 서버 시작 중..."

# 기존 컨테이너 정리
docker rm -f remon-qdrant 2>/dev/null

# Qdrant 실행
docker run -d \
  --name remon-qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  ## 6334 포트는 고성능 데이터 전송용 및 대량 임베딩 삽입용 입니다.
  -v "$(pwd)/data/qdrant:/qdrant/storage" \
  qdrant/qdrant:latest

echo ""
echo "✅ Qdrant 서버 실행 완료"
echo "📊 REST API: http://localhost:6333"
echo "🎨 대시보드: http://localhost:6333/dashboard"
echo ""
echo "확인: docker ps | grep qdrant"
