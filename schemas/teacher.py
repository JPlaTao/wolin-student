from pydantic import BaseModel, Field
from typing import Optional

# 请求模型
class TeacheresUpdata(BaseModel):
    teacher_name: Optional[str] = Field(None, description="老师姓名")
    gender: Optional[str] = Field(None, description="性别：男/女")
    phone: Optional[str] = Field(None, description="11位手机号")
    role: Optional[str] = Field(None, description="角色：counselor/headteacher/lecturer")
