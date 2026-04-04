from pydantic import BaseModel

# 响应模型
class TeacheresUpdata(BaseModel):
    teacher_name: str
    role: str