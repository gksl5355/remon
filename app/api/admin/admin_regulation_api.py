from fastapi import APIRouter, UploadFile, Form
from datetime import date

router = APIRouter(prefix="/admin/regulations", tags=["Admin - Regulation"])

# 예시 데이터
regulations = [
    {"id": 1, "country": "KR", "name": "KR_Tobacco_Label_2025.pdf", "upload_date": "2025-11-08"},
    {"id": 2, "country": "US", "name": "US_Nicotine_Notice.pdf", "upload_date": "2025-11-07"},
    {"id": 3, "country": "JP", "name": "JP_Food_Labeling.pdf", "upload_date": "2025-11-06"},
]

@router.get("")
async def list_regulations(country: str = None, product: str = None):
    return regulations

@router.post("/upload")
async def upload_regulation(file: UploadFile, country: str = Form(...)):
    new_file = {
        "id": len(regulations) + 1,
        "country": country,
        "name": file.filename,
        "upload_date": str(date.today()),
    }
    regulations.append(new_file)
    return {"message": "업로드 성공", "file": new_file}

@router.get("/{file_id}/download/{type}")
async def download_file(file_id: int, type: str):
    return {"message": f"다운로드 요청됨 (id={file_id}, type={type})"}

@router.delete("/{file_id}")
async def delete_regulation(file_id: int):
    global regulations
    regulations = [f for f in regulations if f["id"] != file_id]
    return {"message": "삭제 완료"}
