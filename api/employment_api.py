from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from schemas.emp_schemas import EmploymentUpdate, EmploymentResp
from database import get_db
from dao.employment_dao import *

router = APIRouter(prefix="/employment", tags=["就业管理模块"])


# ------------------------------
# 1. 获取单个学生就业信息
# ------------------------------
@router.get("/students/{stu_id}", response_model=EmploymentResp)
def get_student_employment(stu_id: int, db: Session = Depends(get_db)):
    emp = get_employment_by_stu_id(db, stu_id)
    if not emp:
        raise HTTPException(status_code=404, detail="未找到就业信息")
    return emp


# ------------------------------
# 2. 获取班级所有就业信息
# ------------------------------
@router.get("/class/{class_id}", response_model=List[EmploymentResp])
def get_class_employment(class_id: int, db: Session = Depends(get_db)):
    data = get_employment_by_class_id(db, class_id)
    return data


# ------------------------------
# 3. 更新学生就业信息
# ------------------------------
@router.post("/students/{stu_id}", response_model=EmploymentResp)
def update_student_employment(
    stu_id: int,
    update_data: EmploymentUpdate,
    db: Session = Depends(get_db)
):
    emp = get_employment_by_stu_id(db, stu_id)
    if not emp:
        raise HTTPException(status_code=404, detail="就业记录不存在")

    success = update_employment(db, emp, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="更新失败")

    return emp


# ------------------------------
# 4. 逻辑删除就业信息
# ------------------------------
@router.delete("/delete/{emp_id}")
def delete_employment_api(emp_id: int, db: Session = Depends(get_db)):
    emp = get_employment_by_emp_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")

    success = delete_employment(db, emp)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"detail": "删除成功"}


# ------------------------------
# 5. 恢复就业信息
# ------------------------------
@router.put("/restore/{emp_id}")
def restore_emp(emp_id: int, db: Session = Depends(get_db)):
    success = restore_employment(db, emp_id)
    if not success:
        raise HTTPException(status_code=404, detail="恢复失败")

    return {"detail": "恢复成功"}