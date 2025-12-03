import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

class S3Uploader:
    def __init__(self):
        # 자격 증명 로드
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_DEFAULT_REGION")
        
        # 타겟 ARN (버킷 대신 사용)
        self.target_arn = os.getenv("AWS_S3_ACCESS_POINT_ARN")
        
        # [수정] 경로 프리픽스 로드 (없으면 빈 문자열)
        self.base_prefix = os.getenv("S3_BASE_PREFIX", "")
        self.app_prefix = os.getenv("S3_APP_PREFIX", "")

        # 클라이언트 초기화
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

    def upload_file(self, file_content: bytes, file_name: str, folder: str = "regulation") -> str:
        """
        [경로 조립 로직 추가]
        Base Prefix + App Prefix + Category Folder + Filename
        """
        if not self.target_arn:
            print("❌ AWS_S3_ACCESS_POINT_ARN 설정이 없습니다.")
            return None
            
        # 1. 경로 조립 (빈 값은 걸러내고 /로 연결)
        # 예: team17/raw_data/regulation/hash.pdf
        path_parts = [self.base_prefix, self.app_prefix, folder, file_name]
        # 빈 문자열('')이나 None을 제거하고 '/'로 합침
        s3_key = "/".join([p for p in path_parts if p])
        
        try:
            print(f"☁️ S3 업로드 시도: {s3_key}")
            
            # 2. 업로드 수행
            self.s3_client.put_object(
                Bucket=self.target_arn,
                Key=s3_key,
                Body=file_content,
                ContentType='application/pdf' if file_name.endswith('.pdf') else 'text/plain'
            )
            
            # 3. 저장된 전체 경로 반환 (DB 저장용)
            # Access Point URL이 있다면 앞에 붙여줄 수도 있지만, 
            # 내부 식별용으로는 Key만 있어도 충분하거나 s3:// 프로토콜 사용
            return f"s3://{s3_key}"
            
        except NoCredentialsError:
            print("❌ AWS 자격 증명 오류")
            return None
        except ClientError as e:
            print(f"❌ S3 업로드 실패 (ClientError): {e}")
            return None
        except Exception as e:
            print(f"❌ 알 수 없는 업로드 오류: {e}")
            return None

