#!/bin/bash
# S3에 규제 파일 업로드 스크립트
# Usage: bash scripts/upload_to_s3.sh

# 환경변수 로드
export $(grep '^AWS_' /home/minje/remon/.env | xargs)

# S3 Access Point ARN
ACCESS_POINT_ARN="arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage"
S3_PREFIX="skala2/skala-2.4.17/regulation/US"

# 업로드할 파일들
FILES=(
    "/home/minje/remon/regulation_file/us/Regulation Data A (1).pdf"
    "/home/minje/remon/regulation_file/us/Regulation Data B (1).pdf"

)

echo "🚀 S3 업로드 시작..."

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        s3_key="${S3_PREFIX}/${filename}"
        echo "📤 업로드 중: $filename"
        aws s3api put-object \
            --bucket "${ACCESS_POINT_ARN}" \
            --key "${s3_key}" \
            --body "$file"
        
        if [ $? -eq 0 ]; then
            echo "✅ 업로드 완료: $s3_key"
        else
            echo "❌ 업로드 실패: $filename"
        fi
    else
        echo "⚠️  파일 없음: $file"
    fi
done

echo ""
echo "📋 S3 파일 목록:"
aws s3api list-objects-v2 \
    --bucket "${ACCESS_POINT_ARN}" \
    --prefix "${S3_PREFIX}/" \
    --query 'Contents[].Key' \
    --output text

echo ""
echo "✅ 업로드 완료"
