from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from model.user import User
from model.student import StuBasicInfo
from core.auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, get_current_admin_user
)
from core.exceptions import (
    ValidationException, ConflictException, NotFoundException,
    UnauthorizedException, BusinessException
)
from core.permissions import require_role
from datetime import timedelta
from typing import Optional
from utils.logger import get_logger
from utils.log_decorators import log_api_call, log_sensitive_operation

router = APIRouter(prefix="/auth", tags=["认证"])
logger = get_logger("auth_api")


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"  # 默认角色为普通用户
    stu_id: Optional[int] = None  # 学生注册时可选绑定学号


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    stu_id: Optional[int] = None  # 绑定/解绑学生学号


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    username: str
    role: str
    is_active: bool
    stu_id: Optional[int] = None  # 学生学号


@router.post("/register")
@log_api_call("用户注册")
def register(user: UserCreate, db: Session = Depends(get_db)):
    # 验证角色是否合法
    from core.permissions import VALID_ROLES, REGISTRABLE_ROLES
    if user.role not in VALID_ROLES:
        raise ValidationException(
            message=f"角色必须是以下之一: {', '.join(VALID_ROLES)}",
            field="role",
            detail=f"提供的角色 '{user.role}' 不在允许的角色列表中"
        )
    if user.role not in REGISTRABLE_ROLES:
        raise ValidationException(
            message="该角色不允许自行注册",
            field="role",
            detail=f"'{user.role}' 角色只能由管理员在后台创建"
        )

    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise ConflictException(
            message="用户名已存在",
            detail="该用户名已被其他用户使用，请选择其他用户名"
        )
    hashed = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed, role=user.role)

    # 注册时可选绑定学生学号
    if user.stu_id is not None:
        if user.role != "student":
            raise ValidationException(
                message="仅学生角色可绑定学号",
                field="stu_id"
            )
        student = db.query(StuBasicInfo).filter(
            StuBasicInfo.stu_id == user.stu_id,
            StuBasicInfo.is_deleted == False
        ).first()
        if not student:
            raise ValidationException(
                message="学号不存在",
                field="stu_id",
                detail=f"学号 {user.stu_id} 在系统中不存在"
            )
        existing = db.query(User).filter(User.stu_id == user.stu_id).first()
        if existing:
            raise ConflictException(
                message="该学生已被其他账号绑定",
                detail=f"学号 {user.stu_id} 已被其他用户绑定"
            )
        new_user.stu_id = user.stu_id

    db.add(new_user)
    db.commit()
    return {"msg": "注册成功", "username": user.username, "role": user.role, "stu_id": new_user.stu_id}


@router.post("/login")
@log_api_call("用户登录")
def login(form_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise UnauthorizedException(
            message="用户名或密码错误",
            detail="请检查用户名和密码是否正确"
        )
    # 使用配置中的过期时间
    from core.settings import get_settings
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.jwt.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=expires_delta
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt.access_token_expire_minutes * 60,  # 返回秒数
        "username": user.username,
        "role": user.role,
        "user_id": user.id
    }


@router.get("/me")
@log_api_call("获取当前用户信息")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active
    }


@router.get("/users")
@log_api_call("获取用户列表")
def get_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """获取用户列表（仅管理员）"""
    users = db.query(User).offset(skip).limit(limit).all()
    return {"data": [UserResponse.model_validate(u) for u in users]}


@router.get("/users/{user_id}")
@log_api_call("获取用户详情")
def get_user(
    user_id: int,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """获取单个用户信息（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException(
            resource="用户",
            detail=f"ID为 {user_id} 的用户不存在"
        )
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}")
@log_api_call("更新用户信息")
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """更新用户信息（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException(
            resource="用户",
            detail=f"ID为 {user_id} 的用户不存在"
        )

    if user_update.role is not None:
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    if user_update.stu_id is not None:
        target_role = user_update.role if user_update.role is not None else user.role
        if target_role != "student":
            raise ValidationException(message="仅学生角色可绑定学号", field="stu_id")
        student = db.query(StuBasicInfo).filter(
            StuBasicInfo.stu_id == user_update.stu_id,
            StuBasicInfo.is_deleted == False
        ).first()
        if not student:
            raise ValidationException(message="学号不存在", field="stu_id")
        existing = db.query(User).filter(User.stu_id == user_update.stu_id, User.id != user_id).first()
        if existing:
            raise ConflictException(message="该学生已被其他账号绑定")
        user.stu_id = user_update.stu_id
    # 显式传 null 表示解绑
    if "stu_id" in user_update.model_dump(exclude_unset=True) and user_update.stu_id is None:
        user.stu_id = None

    db.commit()
    db.refresh(user)
    return {"msg": "用户更新成功", "user": user}


@router.delete("/users/{user_id}")
@log_sensitive_operation("删除用户", level="ERROR")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """删除用户（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException(
            resource="用户",
            detail=f"ID为 {user_id} 的用户不存在"
        )

    if user.username == current_user.username:
        raise BusinessException(
            message="不能删除自己的账号",
            detail="不允许删除当前登录的账号"
        )

    db.delete(user)
    db.commit()
    return {"msg": "用户删除成功"}
