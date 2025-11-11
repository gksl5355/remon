from app.core.models import AdminUser
from .base_repository import BaseRepository

class AdminUserRepository(BaseRepository[AdminUser]):
    def __init__(self):
        super().__init__(AdminUser)
