import os
from app.ai_pipeline.preprocess.loader import DocumentLoader

class PreprocessAgent:
    async def run(self, file_path: str, meta_data: dict):
        """
        저장된 파일을 로드하고 텍스트를 추출하여 반환합니다.
        [수정] DocumentLoader가 비동기로 변경됨에 따라 await 키워드 추가
        """
        print(f"\n🤖 [Preprocess Agent] 작동 시작")
        print(f"📄 Target File: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"❌ Error: 파일이 존재하지 않습니다 ({file_path})")
            return None

        # 1. 텍스트 추출 (Loader 사용) - 비동기 호출
        extracted_text = await DocumentLoader.load(file_path)
        
        if not extracted_text:
            print("⚠️ 텍스트 추출 실패 또는 빈 내용입니다.")
            return None

        print(f"✅ 텍스트 추출 완료 (길이: {len(extracted_text)}자)")
        
        # 2. 결과 반환 (추후 LangGraph State 또는 DB 업데이트용)
        # 여기서 추출된 텍스트를 가지고 '요약'이나 '번역' 에이전트로 넘길 수 있습니다.
        result = {
            "status": "success",
            "file_path": file_path,
            "meta_data": meta_data,
            "extracted_text": extracted_text,
            "char_count": len(extracted_text)
        }
        
        return result

# import os
# from app.ai_pipeline.preprocess.loader import DocumentLoader

# class PreprocessAgent:
#     async def run(self, file_path: str, meta_data: dict):
#         """
#         저장된 파일을 로드하고 텍스트를 추출하여 반환합니다.
#         """
#         print(f"\n🤖 [Preprocess Agent] 작동 시작")
#         print(f"📄 Target File: {file_path}")
        
#         if not os.path.exists(file_path):
#             print(f"❌ Error: 파일이 존재하지 않습니다 ({file_path})")
#             return None

#         # 1. 텍스트 추출 (Loader 사용)
#         extracted_text = DocumentLoader.load(file_path)
        
#         if not extracted_text:
#             print("⚠️ 텍스트 추출 실패 또는 빈 내용입니다.")
#             return None

#         print(f"✅ 텍스트 추출 완료 (길이: {len(extracted_text)}자)")
        
#         # 2. 결과 반환 (추후 LangGraph State에 들어갈 내용)
#         return {
#             "status": "success",
#             "file_path": file_path,
#             "meta_data": meta_data,
#             "extracted_text": extracted_text  # 추출된 본문
#         }