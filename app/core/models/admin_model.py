from sqlalchemy import Column, Integer, String
from . import Base

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    admin_user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(50), nullable=False)
