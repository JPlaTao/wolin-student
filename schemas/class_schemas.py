from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

# 不要再导入 TeacherBase！这是无限递归根源
# from schemas.teacher import TeacherBase


class ClassCreate(BaseModel):
    class_name: str = Field(..., min_length=1)
    start_time: Optional[datetime] = None
    head_teacher_id: Optional[int] = Field(None, gt=0)


class ClassUpdate(BaseModel):
    class_name: Optional[str] = Field(None, min_length=1)
    start_time: Optional[datetime] = None
    head_teacher_id: Optional[int] = Field(None, gt=0)


class ClassOut(BaseModel):
    class_id: int
    class_name: str
    start_time: Optional[datetime]
    head_teacher_id: Optional[int] = None
    is_deleted: bool

    class Config:
        from_attributes = True