from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class TeacherBase(BaseModel):
    teacher_id: int
    teacher_name: str
    gender: str
    phone: str
    role: str

    class Config:
        from_attributes = True  # 允许从 SQLAlchemy ORM 对象转换


# 响应模型
class TeacheresUpdata(BaseModel):
    teacher_name: str = Field(..., description="老师姓名")
    gender: str = Field(..., description="性别：男/女")
    phone: str = Field(..., description="11位手机号")
    role: str = Field(..., description="角色：counselor/headteacher/lecturer")
