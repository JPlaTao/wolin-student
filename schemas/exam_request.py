from pydantic import BaseModel
from typing import Optional
from datetime import date


# 新增考试成绩的请求体
class NewExamData(BaseModel):
    stu_id: int
    seq_no: int
    grade: Optional[int] = None
    exam_date: Optional[date] = None


# 修改考试成绩的请求体
class UpdateExamData(BaseModel):
    grade: Optional[int] = None
    exam_date: Optional[date] = None