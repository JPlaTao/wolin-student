"""
角色与权限常量定义

提供统一的角色标识和权限校验工具，供 API 层使用。
"""

from typing import List
from fastapi import Depends
from model.user import User
from core.auth import get_current_user
from core.exceptions import ForbiddenException


# 角色常量
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

# 有效角色列表
VALID_ROLES = [ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT]

# 注册许可角色列表（普通注册可选的角色）
REGISTRABLE_ROLES = [ROLE_STUDENT, ROLE_TEACHER]


def require_role(roles: List[str]):
    """返回一个 FastAPI 依赖，校验当前用户角色是否在允许列表中。

    用法:
        @router.get("/students")
        async def list_students(
            current_user: User = Depends(require_role(["admin", "teacher"]))
        ):
            ...
    """
    async def _role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise ForbiddenException(
                message="权限不足",
                detail=f"需要 {'/'.join(roles)} 角色，当前角色为 {current_user.role}"
            )
        return current_user
    return _role_checker
