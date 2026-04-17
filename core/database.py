"""
数据库连接模块
使用 Settings 配置，支持类型验证
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core.settings import get_settings

settings = get_settings()

engine = create_engine(
    url=settings.database.url,
    pool_size=settings.database.pool_size,
    pool_recycle=settings.database.pool_recycle
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM基类
Base = declarative_base()


# 获取数据库连接
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
