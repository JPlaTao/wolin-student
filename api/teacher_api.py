from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from dao import teacher_dao as dao
from pydantic import ValidationError

from schemas.teacher import TeacheresUpdata

router = APIRouter(
    prefix="/teacher",
    tags=['老师管理模块']
)


# 新增老师
@router.post("/")
def create_teacher(teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    try:
        return dao.create_teacher(db, teacher)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"参数校验失败：{e.errors()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误：{str(e)}")


# 查询单个老师
@router.get("/{teacher_id}")
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    t = dao.get_teacher(db, teacher_id)
    if not t:
        raise HTTPException(status_code=404, detail="老师不存在")
    return t


# 查询所有老师
@router.get("/")
def get_all_teachers(db: Session = Depends(get_db)):
    return dao.get_all_teachers(db)


# 修改老师
@router.put("/{teacher_id}")
def update_teacher(teacher_id: int, teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    t = dao.update_teacher(db, teacher_id, teacher)
    if not t:
        raise HTTPException(status_code=404, detail="老师不存在或已删除")
    return t


# 删除老师
@router.delete("/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    return dao.delete_teacher(db, teacher_id)


# ========================================================
@router.get("/{teacher_id}/head_classes")
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    teacher = dao.get_teacher(db, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="老师不存在或已删除")
    classes = dao.get_head_classes(db, teacher_id)
    return {"msg": "查询成功" if classes else "该老师无管理班级", "data": classes}


@router.get("/{teacher_id}/teach_classes")
def get_teach_classes(teacher_id: int, db: Session = Depends(get_db)):
    return dao.get_teach_classes(db, teacher_id)


@router.get("/{teacher_id}/my_students")
def get_my_students(teacher_id: int, db: Session = Depends(get_db)):
    return dao.get_my_students(db, teacher_id)
