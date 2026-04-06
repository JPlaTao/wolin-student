from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dao.class_dao import (
    get_all_class,
    get_class_by_id,
    create_class,
    update_class,
    delete_class,
    restore_class,
    get_class_teacher
)
from schemas.class_schemas import ClassCreate, ClassUpdate
from schemas.response import ResponseBase
from database import get_db

router = APIRouter(prefix="/class", tags=["班级管理"])


# 获取所有班级 - 返回以class_id为键的字典
@router.get("/", response_model=ResponseBase)
def read_all_classes(
        db: Session = Depends(get_db),
        include_deleted: bool = Query(False, description="是否包含已删除的班级")
):
    classes_list = get_all_class(db, include_deleted=include_deleted)

    # 列表转字典：以 class_id 为键
    classes_dict = {
        str(c["class_id"]): c
        for c in classes_list
    }

    return ResponseBase(
        code=200,
        message="查询成功",
        data=classes_dict
    )


# 获取单个班级
@router.get("/{class_id}", response_model=ResponseBase)
def read_one_class(
        class_id: int,
        db: Session = Depends(get_db),
        include_deleted: bool = Query(False)
):
    cls_dict = get_class_by_id(db, class_id, include_deleted=include_deleted)
    if not cls_dict:
        raise HTTPException(status_code=404, detail="班级不存在")

    return ResponseBase(
        code=200,
        message="查询成功",
        data=cls_dict
    )


# 根据班级ID查授课老师
@router.get("/{class_id}/teachers", response_model=ResponseBase)
def get_class_teachers(
        class_id: int,
        db: Session = Depends(get_db)
):
    teacher_list = get_class_teacher(db, class_id)

    if not teacher_list:
        raise HTTPException(status_code=404, detail="班级不存在或暂无教师授课老师")

    return ResponseBase(
        code=200,
        message="查询成功",
        data=teacher_list
    )


# 创建班级
@router.post("/", response_model=ResponseBase, status_code=201)
def create_new_class(class_data: ClassCreate, db: Session = Depends(get_db)):
    cls_dict = create_class(db, class_data)

    return ResponseBase(
        code=201,
        message="创建成功",
        data=cls_dict
    )


# 更新班级
@router.put("/{class_id}", response_model=ResponseBase)
def update_exist_class(
        class_id: int,
        class_data: ClassUpdate,
        db: Session = Depends(get_db)
):
    cls_dict = update_class(db, class_id, class_data)
    if not cls_dict:
        raise HTTPException(status_code=404, detail="班级不存在")

    return ResponseBase(
        code=200,
        message="更新成功",
        data=cls_dict
    )


# 删除班级
@router.delete("/{class_id}", response_model=ResponseBase)
def delete_exist_class(
        class_id: int,
        db: Session = Depends(get_db),
        hard_delete: bool = Query(False, description="是否硬删除")
):
    result = delete_class(db, class_id, hard_delete=hard_delete)

    # 判断返回类型：False表示班级不存在，字典表示删除成功
    if result is False:
        raise HTTPException(status_code=404, detail="班级不存在")

    msg = "硬删除成功" if hard_delete else "软删除成功"

    return ResponseBase(
        code=200,
        message=msg,
        data=result
    )


# 恢复班级
@router.post("/{class_id}/restore", response_model=ResponseBase)
def restore_deleted_class(class_id: int, db: Session = Depends(get_db)):
    cls_dict = restore_class(db, class_id)
    if not cls_dict:
        raise HTTPException(status_code=404, detail="班级被删除或者不存在")

    return ResponseBase(
        code=200,
        message="恢复成功",
        data=cls_dict
    )
