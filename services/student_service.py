from sqlalchemy.orm import Session
from fastapi import HTTPException

from dao import student_dao, employment_dao
from schemas.student import StudentCreate


def create_student_with_employment(
    db: Session,
    student_data: StudentCreate
):
    """
    创建学生并级联创建空就业记录
    这是一个业务操作，需要协调多个 DAO
    """
    # 1. 创建学生（DAO 层只负责纯数据操作）
    new_student = student_dao.create_student(db, student_data)
    
    # 2. 级联创建空就业记录
    employment_dao.create_empty_employment(
        db,
        new_student['stu_id'],
        new_student['stu_name'],
        new_student['class_id'],
    )
    
    return new_student


def validate_counselor(counselor_id: int, db: Session):
    """校验老师是否是 counselor"""
    from model.teachers import Teacher
    
    counselor = db.query(Teacher).filter(
        Teacher.teacher_id == counselor_id,
        Teacher.role == 'counselor'
    ).first()
    
    if not counselor:
        raise HTTPException(
            status_code=400, 
            detail=f"教师 ID {counselor_id} 不存在或不是 counselor 角色"
        )


def validate_class_exists(class_id: int, db: Session):
    """校验班级是否存在"""
    from model.class_model import Class
    
    class_obj = db.query(Class).filter(
        Class.class_id == class_id
    ).first()
    
    if not class_obj:
        raise HTTPException(status_code=400, detail=f"班级 ID {class_id} 不存在")
