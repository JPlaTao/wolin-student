from pydantic import BaseModel,Field
from datetime import date
from typing import Optional

# 创建用（前端传参）
class EmploymentCreate(BaseModel):
    stu_id: int
    company: Optional[str] = None
    salary: Optional[float] = Field(None, gt=0)
    open_time: Optional[date] = None
    offer_time: Optional[date] = None

# 更新用（前端传参）
class EmploymentUpdate(BaseModel):
    stu_name: Optional[str] = None
    open_time: Optional[date] = None
    offer_time: Optional[date] = None
    company: Optional[str] = None
    salary: Optional[float] = Field(None, gt=0)

# 查询返回用（响应模型）
class EmploymentResp(BaseModel):
    emp_id: int
    stu_id: int
    stu_name: str
    class_id: int
    open_time: Optional[date]
    offer_time: Optional[date]
    company: Optional[str]
    salary: Optional[float]

    model_config = {"from_attributes": True}