from sqlalchemy import Column, Integer, String, Boolean
from core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")  # admin, teacher, student, user
    
    # 邮箱绑定（用户级别配置）
    email_provider = Column(String(20), nullable=True)  # 'qq', '163'
    email_address = Column(String(100), nullable=True)   # 用户邮箱地址
    email_auth_code = Column(String(100), nullable=True)  # 授权码（生产环境应加密存储）
    email_from_name = Column(String(50), nullable=True)   # 发件人昵称