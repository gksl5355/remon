#!/bin/bash
# S3에 규제 파일 업로드 스크립트
# Usage: bash scripts/upload_to_s3.sh

# 파일삭제 명령어 :  

# export $(grep '^AWS_' /home/minje/remon/.env | xargs)
# ACCESS_POINT_ARN="arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage"
# S3_PREFIX="skala2/skala-2.4.17/test/US"

#aws s3 rm "s3://${ACCESS_POINT_ARN}/${S3_PREFIX}/" --recursive


# 환경변수 로드
export $(grep '^AWS_' /home/minje/remon/.env | xargs)

# S3 Access Point ARN
ACCESS_POINT_ARN="arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage"
S3_BASE="skala2/skala-2.4.17/test"

# 국가별 업로드 파일 정의 (S3_PREFIX:LOCAL_FILE)
declare -A UPLOAD_MAP=(
    ["${S3_BASE}/US"]="/home/minje/remon/regulation_file/us/Regulation Data B (1).pdf"
# "/home/minje/remon/regulation_file/us/Regulation Data A (1).pdf"
# "/home/minje/remon/regulation_file/us/practice_us_20251205.pdf"

    # ["${S3_BASE}/RU"]="/home/minje/remon/regulation_file/rs/1. N 123-FZ.pdf"
    # ["${S3_BASE}/ID"]="/home/minje/remon/regulation_file/id/Badan Pengawas Obat dan Makanan.pdf"
)

echo "🚀 S3 업로드 시작..."
echo ""

for s3_prefix in "${!UPLOAD_MAP[@]}"; do
    file="${UPLOAD_MAP[$s3_prefix]}"
    
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        s3_key="${s3_prefix}/${filename}"
        country=$(basename "$s3_prefix")
        
        echo "📤 [$country] 업로드 중: $filename"
        aws s3api put-object \
            --bucket "${ACCESS_POINT_ARN}" \
            --key "${s3_key}" \
            --body "$file"
        
        if [ $? -eq 0 ]; then
            echo "✅ [$country] 업로드 완료: $s3_key"
        else
            echo "❌ [$country] 업로드 실패: $filename"
        fi
    else
        echo "⚠️  파일 없음: $file"
    fi
    echo ""
done

echo "📋 S3 파일 목록:"
for country in US RU ID; do
    echo ""
    echo "[$country]"
    aws s3api list-objects-v2 \
        --bucket "${ACCESS_POINT_ARN}" \
        --prefix "${S3_BASE}/${country}/" \
        --query 'Contents[].Key' \
        --output text
done

echo ""
echo "✅ 모든 업로드 완료"
