from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from dao import exam_dao
from schemas import response, exam_request
from typing import Optional


router_exam = APIRouter(prefix="/exam", tags=["学生成绩管理"])


# 提交考试成绩
@router_exam.post("/", response_model=response.ResponseBase, description="提交考试成绩")
async def exam_submit(
        exam_data: exam_request.NewExamData,
        db: Session = Depends(get_db)
):
    _return = exam_dao.exam_submit(exam_data, db)
    if _return["message"] == "success":
        return response.ResponseBase(data=_return)

    raise HTTPException(status_code=400, detail=_return)


# 修改考试成绩
@router_exam.put("/", response_model=response.ResponseBase, description="修改考试成绩")
async def exam_update(
        exam_data: exam_request.UpdateExamData,
        stu_id: int = Query(description="学生编号"),
        seq_no: int = Query(description="考核序次"),
        db: Session = Depends(get_db)
):
    _return = exam_dao.exam_update(stu_id, seq_no, exam_data, db)
    if _return.endswith('updated'):
        return response.ResponseBase(data=_return)

    raise HTTPException(status_code=400, detail=_return)


# 删除考试成绩（逻辑删除）
@router_exam.delete("/{stu_id}", response_model=response.ResponseBase, description="删除考试成绩(不传seq_no则删除所有stu_id的成绩)")
async def exam_delete(
        stu_id: int,
        seq_no: Optional[int] = None,
        db: Session = Depends(get_db)
):
    _return = exam_dao.exam_delete(stu_id, seq_no, db)
    if _return.endswith('deleted'):
        return response.ResponseBase(data=_return)

    raise HTTPException(status_code=400, detail=_return)
