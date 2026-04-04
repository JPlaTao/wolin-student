from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List
from schemas.teacher import TeacherBase


# ------------------------------
# 班级基础 schema
# ------------------------------
class ClassBase(BaseModel):
    class_name: str
    start_time: datetime
    head_teacher_id: int

    # 数据校验:班级名称不能为空
    @field_validator("class_name")
    def class_name_not_empty(cls, name):
        if not name.strip():
            raise ValueError('班级名称不能为空')
        return name

    # 班主任ID必须是整数
    @field_validator('head_teacher_id')
    def head_teacher_id_positive(cls, id):
        if id <= 0:
            raise ValueError('班主任ID必须是正整数')


# ------------------------------
# 创建班级（前端传参）
# ------------------------------
class ClassCreate(ClassBase):
    pass


# ------------------------------
# 更新班级（可选字段）
# ------------------------------
class ClassUpdate(BaseModel):
    class_name: Optional[str] = None
    start_time: Optional[datetime] = None
    head_teacher_id: Optional[int] = None

    @field_validator("class_name", mode='before')
    def class_name_not_empty_if_provied(cls, name):
        if name is not None and not name.strip():
            raise ValueError('班级名称不能为空')
        return name

    # 班主任ID必须是整数
    @field_validator('head_teacher_id')
    def head_teacher_id_positive_if_provied(cls, id):
        if id is not None and id <= 0:
            raise ValueError('班主任ID必须是正整数')


# ------------------------------
# 返回给前端的完整班级数据
# ------------------------------
class ClassOut(ClassBase):
    class_id: int
    head_teacher_info: Optional[TeacherBase] = None

    # teachers: Optional[List[TeacherBase]] = None  # 授课老师列表

    class Config:
        from_attributes = True  # 关键：让Pydantic支持SQLAlchemy模型
