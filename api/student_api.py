from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dao.employment_dao import create_empty_employment
from database import get_db
from dao import student_dao
from schemas.student import StudentCreate, StudentUpdate, Student, StudentQuery
from schemas import response
from typing import Optional

router = APIRouter(prefix="/students", tags=["学生管理"])


# 创建新学生
@router.post("/", response_model=response.ResponseBase)
def create_student(
        new_student_data: StudentCreate,
        db: Session = Depends(get_db)
):
    new_student = student_dao.create_student(new_student_data, db)

    #student_respond = Student.model_validate(new_student)
    # 级联创建就业信息 空记录
    create_empty_employment(
        db,
        new_student['stu_id'],
        new_student['stu_name'],
        new_student['class_id'],
    )
    return response.ResponseBase(
        data=new_student
    )


# 按条件查询学生
@router.get("/", response_model=response.ListResponse)
def get_students(
        db: Session = Depends(get_db),
        stu_id: Optional[int] = Query(None, description="按学生编号查询"),
        stu_name: Optional[str] = Query(None, description="按学生姓名查询"),
        class_id: Optional[int] = Query(None, description="按班级编号查询")
):
    students = student_dao.get_students(
        db,
        stu_id=stu_id,
        stu_name=stu_name,
        class_id=class_id
    )
    return response.ListResponse(
        data=students,
        total=len(students)
    )


# 更新学生信息
@router.put("/{stu_id}", response_model=response.ResponseBase)
def update_student(
        stu_id: int,
        update_data: StudentUpdate,  # 请求体
        db: Session = Depends(get_db)
):
    # 调用更新方法
    is_update_student = student_dao.update_student(db, stu_id, update_data)

    if not is_update_student:
        raise HTTPException(status_code=400, detail="没有这个学生")

    # is_update_student = Student.model_validate(is_update_student)
    return response.ResponseBase(
        data=is_update_student
    )


# 删除学生(逻辑删除)
@router.delete("/{stu_id}", response_model=response.ResponseBase)
def delete_student(
        stu_id: int,
        db: Session = Depends(get_db)
):
    # 调用更新方法
    is_delete_student = student_dao.delete_student(db, stu_id)

    if is_delete_student == '不存在这个学生或已被删除':
        raise HTTPException(status_code=400, detail="没有这个学生或已被删除")
    return response.ResponseBase(
        message=is_delete_student,
        data=None
    )
