import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, ClientError

# 1. 환경 변수 로드
load_dotenv()

def list_s3_files():
    print("\n🕵️ [S3 파일 검증] 업로드된 파일 목록 조회 중...\n")

    # .env에서 정보 가져오기
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION")
    target_arn = os.getenv("AWS_S3_TARGET_ARN")

    if not target_arn:
        print("❌ Error: .env에 AWS_S3_TARGET_ARN 값이 없습니다.")
        return

    try:
        # S3 클라이언트 연결
        s3 = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        # 2. 파일 목록 조회 (Access Point ARN을 Bucket 이름 대신 사용)
        response = s3.list_objects_v2(Bucket=target_arn)

        # 3. 결과 출력
        if 'Contents' in response:
            print(f"✅ 접속 성공! (Target: {target_arn})\n")
            print(f"{'파일 크기(KB)':<15} | {'수정 시간':<25} | {'파일 경로 (Key)'}")
            print("-" * 80)

            count = 0
            for obj in response['Contents']:
                key = obj['Key']
                size_kb = round(obj['Size'] / 1024, 2)
                last_modified = obj['LastModified'].strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"{size_kb:<15} | {last_modified:<25} | {key}")
                count += 1
            
            print("-" * 80)
            print(f"📦 총 발견된 파일: {count}개")
        else:
            print(f"✅ 접속 성공! 하지만 아직 업로드된 파일이 없습니다.")
            print(f"(Target: {target_arn})")

    except NoCredentialsError:
        print("❌ 인증 실패: AWS 키를 확인하세요.")
    except ClientError as e:
        print(f"❌ 조회 실패 (권한 부족 또는 설정 오류): {e}")
    except Exception as e:
        print(f"❌ 알 수 없는 오류: {e}")

if __name__ == "__main__":
    list_s3_files()