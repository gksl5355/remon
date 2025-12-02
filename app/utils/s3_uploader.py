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

# import os
# import boto3
# from botocore.exceptions import NoCredentialsError, ClientError

# class S3Uploader:
#     def __init__(self):
#         # .env에서 로드
#         self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
#         self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
#         self.region = os.getenv("AWS_REGION")
        
#         # Access Point ARN을 버킷 타겟으로 사용
#         self.target_arn = os.getenv("AWS_S3_TARGET_ARN")

#         # Boto3 클라이언트 초기화
#         self.s3_client = boto3.client(
#             's3',
#             aws_access_key_id=self.access_key,
#             aws_secret_access_key=self.secret_key,
#             region_name=self.region
#         )

#     def upload_file(self, file_content: bytes, file_name: str, folder: str = "raw_data") -> str:
#         """
#         S3 Access Point로 파일 업로드
#         Return: 다운스트림에서 사용할 S3 URI 또는 식별자
#         """
#         if not self.target_arn:
#             print("❌ AWS_S3_TARGET_ARN 설정이 없습니다.")
#             return None
            
#         # S3 내 저장 경로 (Key) 예: regulation/uuid_1234.pdf
#         s3_key = f"{folder}/{file_name}"
        
#         try:
#             print(f"☁️ S3 업로드 시도: {s3_key}")
            
#             # Bucket 파라미터에 ARN을 넣으면 됩니다.
#             self.s3_client.put_object(
#                 Bucket=self.target_arn,
#                 Key=s3_key,
#                 Body=file_content
#             )
            
#             # 저장된 경로 반환
#             # (참고: Access Point 사용 시 s3://bucket-name/... 형태가 아닐 수 있으므로
#             #  명확한 식별을 위해 Key를 포함한 경로를 반환합니다.)
#             return f"s3-access-point://{s3_key}"
            
#         except NoCredentialsError:
#             print("❌ AWS 자격 증명 오류")
#             return None
#         except ClientError as e:
#             print(f"❌ S3 업로드 실패 (ClientError): {e}")
#             return None
#         except Exception as e:
#             print(f"❌ 알 수 없는 업로드 오류: {e}")
#             return None

# import os
# import boto3
# from botocore.exceptions import NoCredentialsError

# class S3Uploader:
#     def __init__(self):
#         self.bucket = os.getenv("AWS_BUCKET_NAME")
#         self.s3 = boto3.client(
#             's3',
#             aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
#             aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
#             region_name=os.getenv("AWS_REGION", "ap-northeast-2")
#         )

#     def upload_file(self, file_content: bytes, file_name: str, folder: str = "raw_data") -> str:
#         """
#         S3에 파일을 업로드하고 S3 URI를 반환합니다.
#         예: s3://remon-bucket/raw_data/1234.pdf
#         """
#         if not self.bucket:
#             # S3 설정이 없으면 그냥 로컬 경로 반환 (테스트용)
#             return None
            
#         s3_key = f"{folder}/{file_name}"
        
#         try:
#             self.s3.put_object(
#                 Bucket=self.bucket,
#                 Key=s3_key,
#                 Body=file_content
#             )
#             # S3 URI 반환 (팀 설계에 맞춘 포맷)
#             return f"s3://{self.bucket}/{s3_key}"
            
#         except NoCredentialsError:
#             print("❌ AWS 자격 증명이 없습니다.")
#             return None
#         except Exception as e:
#             print(f"❌ S3 업로드 실패: {e}")
#             return None