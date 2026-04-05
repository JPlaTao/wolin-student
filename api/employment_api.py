from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# 导入响应类
from schemas.response import ResponseBase, ListResponse
# 导入就业相关模型
from schemas.emp_schemas import EmploymentUpdate, EmploymentResp
# 数据库依赖
from database import get_db
# 按需导入dao函数
from dao.employment_dao import (
    get_employment_by_stu_id,
    get_employment_by_class_id,
    update_employment,
    delete_employment,
    restore_employment,
    get_employment_by_emp_id
)

router = APIRouter(prefix="/employment", tags=["就业管理模块"])


# ------------------------------
# 1. 获取单个学生就业信息
# ------------------------------
@router.get("/students/{stu_id}", response_model=ResponseBase)
def get_student_employment(stu_id: int, db: Session = Depends(get_db)):
    emp = get_employment_by_stu_id(db, stu_id)
    if not emp:
        raise HTTPException(status_code=404, detail="未找到就业信息")

    emp_data = EmploymentResp.model_validate(emp)
    return ResponseBase(
        code=200,
        message="查询成功",
        data=emp_data
    )

# ------------------------------
# 2. 获取班级所有就业信息（列表 + 总数）
# ------------------------------
@router.get("/class/{class_id}", response_model=ListResponse)
def get_class_employment(class_id: int, db: Session = Depends(get_db)):
    data = get_employment_by_class_id(db, class_id)
    list_data = [EmploymentResp.model_validate(item) for item in data]
    return ListResponse(
        code=200,
        message="查询成功",
        data=list_data,
        total=len(list_data)
    )


# ------------------------------
# 3. 更新学生就业信息
# ------------------------------
@router.post("/students/{stu_id}", response_model=ResponseBase)
def update_student_employment(
        stu_id: int,
        update_data: EmploymentUpdate,
        db: Session = Depends(get_db)
):
    emp = get_employment_by_stu_id(db, stu_id)
    if not emp:
        raise HTTPException(status_code=404, detail="就业记录不存在")

    updated_emp = update_employment(db, emp, update_data)
    if not updated_emp:
        raise HTTPException(status_code=500, detail="更新失败")

    updated_data = EmploymentResp.model_validate(updated_emp)
    return ResponseBase(
        code=200,
        message="更新成功",
        data=updated_data
    )


# ------------------------------
# 4. 逻辑删除就业信息
# ------------------------------
@router.delete("/delete/{emp_id}", response_model=ResponseBase)
def delete_employment_api(emp_id: int, db: Session = Depends(get_db)):
    emp = get_employment_by_emp_id(db, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")

    success = delete_employment(db, emp)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return ResponseBase(
        code=200,
        message="删除成功",
        data=None
    )


# ------------------------------
# 5. 恢复就业信息
# ------------------------------
@router.put("/restore/{emp_id}", response_model=ResponseBase)
def restore_emp(emp_id: int, db: Session = Depends(get_db)):
    success = restore_employment(db, emp_id)
    if not success:
        raise HTTPException(status_code=404, detail="恢复失败")

    return ResponseBase(
        code=200,
        message="恢复成功",
        data=None
    )