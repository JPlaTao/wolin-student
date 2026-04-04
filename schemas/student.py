from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    stu_name: str = Field(..., min_length=1, max_length=20, description="学生姓名")
    class_id: int = Field(..., gt=0, description="班级ID")
    native_place: str = Field(..., max_length=50, description="籍贯")
    graduated_school: str = Field(..., max_length=50, description="毕业院校")
    major: str = Field(..., max_length=50, description="专业")
    admission_date: datetime = Field(..., description="入学日期")
    graduation_date: datetime = Field(..., description="毕业日期")
    education: str = Field(..., max_length=20, description="学历")
    advisor_id: Optional[int] = Field(None, description="顾问ID")
    age: int = Field(..., gt=0, lt=150, description="年龄")
    gender: str = Field(..., pattern="^(男|女)$", description="性别：男/女")


class StudentUpdate(BaseModel):
    """更新学生请求（全部可选）"""
    stu_name: Optional[str] = Field(None, max_length=20)
    class_id: Optional[int] = Field(None, gt=0)
    native_place: Optional[str] = Field(None, max_length=50)
    graduated_school: Optional[str] = Field(None, max_length=50)
    major: Optional[str] = Field(None, max_length=50)
    admission_date: Optional[datetime] = None
    graduation_date: Optional[datetime] = None
    education: Optional[str] = Field(None, max_length=20)
    advisor_id: Optional[int] = None
    age: Optional[int] = Field(None, gt=0, lt=150)
    gender: Optional[str] = Field(None, pattern="^(男|女)$")


class StudentQuery(BaseModel):
    """查询学生参数（Query 参数用，可选）"""
    stu_id: Optional[int] = None
    stu_name: Optional[str] = None
    class_id: Optional[int] = None
