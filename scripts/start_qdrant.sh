#!/bin/bash
# Qdrant 도커 컨테이너 실행
# Qdrant 컬렉션 내 전체포인트 삭제: curl -X DELETE "http://localhost:6333/collections/{collection_name}/points" -H "accept: application/json" -H "Content-Type: application/json" -d "{\"points\": [1, 2, 3]}"
# Qdrant 컬랙션 내 전체포인트 삭제:(/skala-2.4.17-regulation 컬렉션 예시)
# curl -k -X POST "https://qdrant.skala25a.project.skala-ai.com/collections/skala-2.4.17-regulation/points/delete" \
#   -H "api-key: Skala25a!23$" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "filter": {}
#   }'



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
