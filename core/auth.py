from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from core.database import get_db
from core.settings import get_settings
from model.user import User
from core.exceptions import UnauthorizedException, ForbiddenException, BusinessException

settings = get_settings()
SECRET_KEY = settings.jwt.secret_key
ALGORITHM = settings.jwt.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt.access_token_expire_minutes

# 使用 pbkdf2_sha256 代替 bcrypt，避免 72 字节限制和版本兼容问题
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise UnauthorizedException(
                message="无效的认证凭据",
                detail="Token中未包含有效的用户信息"
            )
    except JWTError:
        raise UnauthorizedException(
            message="Token无效或已过期",
            detail="请重新登录以获取有效的访问令牌"
        )
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise UnauthorizedException(
            message="用户不存在",
            detail="Token对应的用户不存在，可能已被删除"
        )
    if not user.is_active:
        raise ForbiddenException(
            message="用户已被禁用",
            detail="该账号已被管理员禁用，请联系管理员"
        )
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise BusinessException(
            message="未激活的用户",
            detail="当前用户账号未激活，请联系管理员"
        )
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise ForbiddenException(
            message="权限不足",
            detail="仅管理员可访问此资源"
        )
    return current_user
