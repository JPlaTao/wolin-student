from pydantic import BaseModel
from typing import Optional

class TeacherBase(BaseModel):
    teacher_id:int
    teacher_name:str
    role:str

    class Config:
        from_attributes = True  # 关键：让Pydantic支持SQLAlchemy模型


class TeacheresUpdata(BaseModel):
    teacher_name: str
    role: str