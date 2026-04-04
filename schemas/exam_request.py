from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


# 新增考试成绩的请求体
class NewExamData(BaseModel):
    stu_id: int
    seq_no: int
    grade: int = Field(default=0, ge=0, le=100, description="考试分数(0~100分)")
    exam_date: Optional[date] = None


# 修改考试成绩的请求体
class UpdateExamData(BaseModel):
    grade: int = Field(default=0, ge=0, le=100, description="考试分数(0~100分)")
    exam_date: Optional[date] = None