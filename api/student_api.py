from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from model.user import User
from services import student_service
from dao import student_dao
from schemas.student import StudentCreate, StudentUpdate
from schemas import response
from core.exceptions import ValidationException, NotFoundException, BusinessException
from typing import Optional
from utils.logger import get_logger
from utils.log_decorators import log_api_call, log_sensitive_operation

router = APIRouter(prefix="/students", tags=["学生管理"])
logger = get_logger("student_api")


# 创建新学生
@router.post("/", response_model=response.ResponseBase)
@log_api_call("创建学生")
def create_student(
        request: Request,
        new_student_data: StudentCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        # 1. 业务校验（Service 层）
        student_service.validate_counselor(new_student_data.advisor_id, db)
        student_service.validate_class_exists(new_student_data.class_id, db)
        
        # 2. 执行业务操作（Service 层协调多个 DAO）
        new_student = student_service.create_student_with_employment(db, new_student_data)
        
        return response.ResponseBase(
            data=new_student
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建学生失败: {str(e)}")
        raise


# 按条件查询学生
@router.get("/", response_model=response.ListResponse)
@log_api_call("查询学生")
def get_students(
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
        stu_id: Optional[int] = Query(None, description="按学生编号查询"),
        stu_name: Optional[str] = Query(None, description="按学生姓名查询"),
        class_id: Optional[int] = Query(None, description="按班级编号查询")
):
    try:
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
    except Exception as e:
        logger.error(f"查询学生失败: {str(e)}")
        raise


# 更新学生信息
@router.put("/{stu_id}", response_model=response.ResponseBase)
@log_api_call("更新学生")
def update_student(
        request: Request,
        stu_id: int,
        update_data: StudentUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        # 业务校验：如果要更新班级或顾问，需要校验
        if update_data.class_id is not None:
            student_service.validate_class_exists(update_data.class_id, db)
        if update_data.advisor_id is not None:
            student_service.validate_counselor(update_data.advisor_id, db)

        # 数据操作
        is_update_student = student_dao.update_student(db, stu_id, update_data)

        if not is_update_student:
            logger.error(f"更新失败: 学生 ID={stu_id} 不存在")
            raise NotFoundException(
                resource="学生",
                detail=f"ID为 {stu_id} 的学生不存在"
            )

        return response.ResponseBase(
            data=is_update_student
        )
    except Exception:
        raise


# 删除学生(逻辑删除)
@router.delete("/{stu_id}", response_model=response.ResponseBase)
@log_sensitive_operation("删除学生", level="WARNING")
def delete_student(
        request: Request,
        stu_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        is_delete_student = student_dao.delete_student(db, stu_id)

        if is_delete_student == '不存在这个学生或已被删除':
            logger.error(f"删除失败: 学生 ID={stu_id} 不存在或已被删除")
            raise NotFoundException(
                resource="学生",
                detail=f"ID为 {stu_id} 的学生不存在或已被删除"
            )

        return response.ResponseBase(
            message=is_delete_student,
            data=None
        )
    except Exception:
        raise
