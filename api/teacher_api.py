from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from dao import teacher_dao as dao
# 导入设置好的模型
from schemas.teacher import TeacheresUpdata, TeacherBase
# 导入通用响应模型
from schemas.response import ResponseBase, ListResponse



router = APIRouter(
    prefix="/teacher",
    tags=['老师管理模块']
)


# 新增老师
@router.post("/", response_model=ResponseBase)
def create_teacher(teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    data = dao.create_teacher(db, teacher)
    return ResponseBase(
        data=data
    )


# 查询单个老师
@router.get("/{teacher_id}", response_model=ResponseBase)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    data = dao.get_teacher(db, teacher_id)
    if not data:
        return ResponseBase(code=404, message="老师不存在", data=None)

    return ResponseBase(
        data=data  # 直接用！
    )


# 查询所有老师
@router.get("/", response_model=ListResponse)
def get_all_teachers(db: Session = Depends(get_db)):
    data = dao.get_all_teachers(db)
    return ListResponse(
        data=data,
        total=len(data)
    )


# 修改老师
@router.put("/{teacher_id}", response_model=ResponseBase)
def update_teacher(teacher_id: int, teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    data = dao.update_teacher(db, teacher_id, teacher)
    if not data:
        return ResponseBase(code=404, message="老师不存在或已删除", data=None)

    return ResponseBase(
        message="修改成功",
        data=data
    )



# 删除老师
@router.delete("/{teacher_id}", response_model=ResponseBase)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    success = dao.delete_teacher(db, teacher_id)
    if not success:
        return ResponseBase(code=404, message="老师不存在或已删除", data=None)

    return ResponseBase(
        message="删除成功",
        data=None
    )


# ========================================================
@router.get("/{teacher_id}/head_classes", response_model=ResponseBase)
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    data = dao.get_head_classes(db, teacher_id)
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    return ResponseBase(data=data)

@router.get("/{teacher_id}/teach_classes", response_model=ResponseBase)
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    # ✅ 直接查班级，不查老师！
    data = dao.get_teach_classes(db, teacher_id)

    # 判断是否是提示文字（老师不存在/无班级）
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    return ResponseBase(data=data)
@router.get("/{teacher_id}/my_students",response_model=ResponseBase)
def get_my_students(teacher_id: int, db: Session = Depends(get_db)):
    data = dao.get_my_students(db, teacher_id)
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    return ResponseBase(data=data)
