from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# 导入响应类
from schemas.response import ResponseBase, ListResponse
# 导入就业相关模型
from schemas.emp_schemas import EmploymentCreate, EmploymentUpdate, EmploymentResp
from model.employment import Employment
from model.student import StuBasicInfo
# 数据库依赖
from core.database import get_db
# 导入认证依赖
from core.auth import get_current_user
from core.permissions import require_role
from model.user import User
# 导入dao函数
from dao.employment_dao import *


router = APIRouter(prefix="/employment", tags=["就业管理模块"])


# ------------------------------
# 0. 新增就业记录
# ------------------------------
@router.post("/", response_model=ResponseBase)
def create_employment(
    create_data: EmploymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "teacher"]))
):
    student = db.query(StuBasicInfo).filter(
        StuBasicInfo.stu_id == create_data.stu_id,
        StuBasicInfo.is_deleted == False
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    emp = create_employment_record(
        db,
        stu_id=create_data.stu_id,
        stu_name=student.stu_name,
        class_id=student.class_id,
        open_time=create_data.open_time,
        offer_time=create_data.offer_time,
        company=create_data.company,
        salary=create_data.salary
    )
    return ResponseBase(
        code=200,
        message="新增成功",
        data=EmploymentResp.model_validate(emp)
    )


# ------------------------------
# 1. 获取单个学生就业信息
# ------------------------------
@router.get("/students/{stu_id}", response_model=ResponseBase)
def get_student_employment(stu_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "teacher"]))):
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
def get_class_employment(class_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "teacher"]))):
    data = get_employment_by_class_id(db, class_id)
    list_data = [EmploymentResp.model_validate(item) for item in data]
    return ListResponse(
        code=200,
        message="查询成功",
        data=list_data,
        total=len(list_data)
    )

# ------------------------------
# 3. 多条件查询就业信息（学生编号 + 公司名 + 工资范围）
# ------------------------------
@router.get("/query", response_model=ListResponse)
def query_employment(
    stu_id: int = None,       # 学生编号（可选）
    company: str = None,      # 公司名称（模糊查询，可选）
    min_salary: int = None,   # 最低工资（可选）
    max_salary: int = None,   # 最高工资（可选）
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "teacher"]))
):
    # 基础查询：未删除的记录
    query = db.query(Employment).filter(Employment.is_deleted == False)

    # 拼接查询条件
    if stu_id is not None:
        query = query.filter(Employment.stu_id == stu_id)
    if company is not None:
        # 公司名模糊匹配
        query = query.filter(Employment.company.like(f"%{company}%"))
    if min_salary is not None:
        query = query.filter(Employment.salary >= min_salary)
    if max_salary is not None:
        query = query.filter(Employment.salary <= max_salary)

    # 执行查询
    data = query.all()
    list_data = [EmploymentResp.model_validate(item) for item in data]

    return ListResponse(
        code=200,
        message="查询成功",
        data=list_data,
        total=len(list_data)
    )
# ------------------------------
# 4. 更新学生就业信息
# ------------------------------
@router.put("/students/{stu_id}", response_model=ResponseBase)
def update_student_employment(
        stu_id: int,
        update_data: EmploymentUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_role(["admin", "teacher"]))
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
# 5. 逻辑删除就业信息
# ------------------------------
@router.delete("/delete/{emp_id}", response_model=ResponseBase)
def delete_employment_api(emp_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "teacher"]))):
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
# 6. 恢复就业信息
# ------------------------------
@router.put("/restore/{emp_id}", response_model=ResponseBase)
def restore_emp(emp_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["admin", "teacher"]))):
    success = restore_employment(db, emp_id)
    if not success:
        raise HTTPException(status_code=404, detail="恢复失败")

    return ResponseBase(
        code=200,
        message="恢复成功",
        data=None
    )