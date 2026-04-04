from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from dao.class_dao import (
    get_all_class,
    get_class_by_id,
    create_class,
    update_class,
    delete_class
)
from schemas.class_schemas import ClassCreate, ClassUpdate, ClassOut
from database import get_db  # 你的数据库连接

router = APIRouter(prefix="/class", tags=["班级管理"])


# 获取所有班级
@router.get("/", response_model=List[ClassOut])
def read_all_classes(db: Session = Depends(get_db)):
    return get_all_class(db)


# 获取单个班级
@router.get("/{class_id}", response_model=ClassOut)
def read_one_class(class_id: int, db: Session = Depends(get_db)):
    cls = get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    return cls


# 创建班级
@router.post("/", response_model=ClassOut)
def create_new_class(class_data: ClassCreate, db: Session = Depends(get_db)):
    return create_class(db, class_data)


# 更新班级
@router.put("/{class_id}", response_model=ClassOut)
def update_exist_class(
        class_id: int,
        class_data: ClassUpdate,
        db: Session = Depends(get_db)
):
    cls = update_class(db, class_id, class_data)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    return cls


# 删除班级
@router.delete("/{class_id}")
def delete_exist_class(class_id: int, db: Session = Depends(get_db)):
    if not delete_class(db, class_id):
        raise HTTPException(status_code=404, detail="班级不存在")
    return {"message": "删除成功"}
