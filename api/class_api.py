from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from dao.class_dao import (
    get_all_class,
    get_class_by_id,
    create_class,
    update_class,
    delete_class,
    restore_class  # 新增导入恢复函数
)
from schemas.class_schemas import ClassCreate, ClassUpdate, ClassOut
from database import get_db  # 你的数据库连接

router = APIRouter(prefix="/class", tags=["班级管理"])


# 获取所有班级
@router.get("/", response_model=List[ClassOut])
def read_all_classes(
        db: Session = Depends(get_db),
        include_deleted: bool = Query(False, description="是否包含已删除的班级")
):
    return get_all_class(db, include_deleted=include_deleted)


# 获取单个班级
@router.get("/{class_id}", response_model=ClassOut)
def read_one_class(
        class_id: int,
        db: Session = Depends(get_db),
        include_deleted: bool = Query(False)
):
    cls = get_class_by_id(db, class_id, include_deleted=include_deleted)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    return cls


# 创建班级
@router.post("/", response_model=ClassOut, status_code=201)
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


# 删除班级  [新增]查询函数
@router.delete("/{class_id}")
def delete_exist_class(
        class_id: int,
        db: Session = Depends(get_db),
        hard_delete: bool = Query(False, description="是否硬删除")
):
    if not delete_class(db, class_id, hard_delete=hard_delete):
        raise HTTPException(status_code=404, detail="班级不存在")
    msg = "硬删除成功" if hard_delete else "软删除成功"
    return {"message": msg}


# 恢复接口
@router.post("/{class_id}/restore")
def restore_deleted_class(class_id: int, db: Session = Depends(get_db)):
    if not restore_class(db, class_id):
        raise HTTPException(status_code=404, detail="班级被删除或者不存在")
    return {"message": "恢复成功"}
