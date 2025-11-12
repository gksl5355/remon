# api/auth_api.py
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt

SECRET_KEY = "supersecret"
ALGORITHM = "HS256"

router = APIRouter(tags=["Auth"])

# 임시 블랙리스트 저장소
token_blacklist = set()

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest):
    """
    로그인: 올바른 계정이면 JWT 발급
    """
    if req.username == "admin" and req.password == "1234":
        payload = {
            "sub": req.username,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/logout")
def logout(authorization: str = Header(None)):
    """
    로그아웃: 전달된 토큰을 블랙리스트에 등록
    """
    if not authorization:
        raise HTTPException(status_code=400, detail="Authorization header missing")

    # 헤더에서 'Bearer ' 부분 제거
    token = authorization.replace("Bearer ", "")

    # 토큰 유효성 검사
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token already expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 블랙리스트에 추가
    token_blacklist.add(token)
    return {"message": "Successfully logged out"}


def is_token_blacklisted(token: str) -> bool:
    """토큰이 블랙리스트에 등록되었는지 확인"""
    return token in token_blacklist
