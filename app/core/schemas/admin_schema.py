from pydantic import BaseModel, Field
from typing import Optional

class AdminUserBase(BaseModel):
    """관리자 기본 스키마"""
    username: str = Field(..., min_length=3, max_length=50, description="사용자명")

class AdminUserCreate(AdminUserBase):
    """관리자 생성 스키마"""
    password: str = Field(..., min_length=8, max_length=50, description="비밀번호")

class AdminUserUpdate(BaseModel):
    """관리자 수정 스키마"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=50)

class AdminUserResponse(AdminUserBase):
    """관리자 응답 스키마"""
    admin_user_id: int
    
    class Config:
        from_attributes = True

class AdminUserLogin(BaseModel):
    """로그인 요청 스키마"""
    username: str
    password: str
