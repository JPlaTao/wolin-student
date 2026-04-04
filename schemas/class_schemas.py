from pydantic import BaseModel, Field  # 【修改】去掉了 field_validator，改用 Field
from datetime import datetime
from typing import Optional, List  # 【修改】List 没用到，可以去掉
from schemas.teacher import TeacherBase


# 【修改】整个 ClassBase 类删除，不再使用继承


# 【修改】ClassCreate 不再继承 ClassBase，独立定义
class ClassCreate(BaseModel):
    class_name: str = Field(..., min_length=1)  # 用 Field 替代 validator
    start_time: datetime
    head_teacher_id: Optional[int] = Field(None, gt=0)  # int → Optional[int]，用 Field 替代 validator


# 【修改】ClassUpdate 的验证器简化
class ClassUpdate(BaseModel):
    class_name: Optional[str] = Field(None, min_length=1)  # 【修改】用 Field 替代 validator
    start_time: Optional[datetime] = None
    head_teacher_id: Optional[int] = Field(None, gt=0)  # 【修改】用 Field 替代 validator

    # 【修改】去掉了两个 field_validator


class ClassOut(BaseModel):
    class_id: int
    class_name: str  # 【修改】加上这行
    start_time: datetime
    head_teacher_id: Optional[int] = None  # 【修改】Optional 明确写出
    head_teacher_info: Optional[TeacherBase] = None
    is_deleted: bool  # 返回软删除状态

    class Config:
        from_attributes = True
