

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.models.admin_model import AdminUser
from .base_repository import BaseRepository

class AdminUserRepository(BaseRepository[AdminUser]):
    """관리자 사용자 Repository"""
    
    def __init__(self):
        super().__init__(AdminUser)
    
    async def get_by_username(
        self,
        db: AsyncSession,
        username: str
    ) -> Optional[AdminUser]:
        """
        사용자명으로 관리자 조회 (로그인용)
        """
        # 기술적 검증
        if not username or len(username) < 3:
            raise ValueError("username must be at least 3 characters")
        
        result = await db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        return result.scalar_one_or_none()
    
    async def verify_password(
        self,
        admin_user: AdminUser,
        password: str
    ) -> bool:
        """
        비밀번호 검증
        
        Note:
            실제로는 해싱된 비밀번호와 비교해야 함
            여기서는 기술적 검증만 수행
        """
        # 기술적 검증
        if not password:
            return False
        
        # 실제 비밀번호 비교 로직은 Service 계층에서 처리
        # Repository는 데이터만 제공
        return admin_user.password == password  # ⚠️ 임시, 실제로는 해싱 필요
