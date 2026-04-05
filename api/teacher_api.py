from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from dao import teacher_dao as dao
# 导入设置好的模型
from schemas.teacher import TeacheresUpdata
# 导入通用响应模型
from schemas.response import ResponseBase, ListResponse

router = APIRouter(
    prefix="/teacher",
    tags=['老师管理模块']
)


# 新增老师
@router.post("/", response_model=ResponseBase)
def create_teacher(teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    # 接收前端传的老师数据（自动校验格式） 自动获取数据库连接（Session）
    # 调用dao层,把数据存入数据库
    data = dao.create_teacher(db, teacher)
    # 返回统一响应模型到前端
    return ResponseBase(
        data=data
    )


# 查询单个老师
@router.get("/{teacher_id}", response_model=ResponseBase)
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    # 校验前端返回的teacher_id是否为int类型 自动获取数据库连接（Session）
    # 调用 dao，根据ID查老师
    data = dao.get_teacher(db, teacher_id)
    # 如果没查到 → 返回404
    if not data:
        return ResponseBase(code=404, message="老师不存在", data=None)
    return ResponseBase(
        data=data
    )


# 查询所有老师
@router.get("/", response_model=ListResponse)
def get_all_teachers(db: Session = Depends(get_db)):
    # 调用 DAO，获取所有老师列表
    data = dao.get_all_teachers(db)
    # 返回带总数的统一响应格式（列表+total）
    return ListResponse(
        data=data,
        total=len(data)
    )


# 修改老师
@router.put("/{teacher_id}", response_model=ResponseBase)
def update_teacher(teacher_id: int, teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    # 调用 dao修改老师数据
    data = dao.update_teacher(db, teacher_id, teacher)
    # 没查到
    if not data:
        return ResponseBase(code=404, message="老师不存在或已删除", data=None)
    # 查到了
    return ResponseBase(
        message="修改成功",
        data=data
    )


# 删除老师（逻辑删除）
@router.delete("/{teacher_id}", response_model=ResponseBase)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    # 调用 dao 删除（标记 is_deleted=True）
    success = dao.delete_teacher(db, teacher_id)
    # 如果老师不存在
    if not success:
        return ResponseBase(code=404, message="老师不存在或已删除", data=None)
    # 删除成功
    return ResponseBase(
        message="删除成功",
        data=None
    )

# ========================================================
@router.get("/{teacher_id}/head_classes", response_model=ResponseBase)
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    # 调用 dao. 查询班主任所带的班
    data = dao.get_head_classes(db, teacher_id)
    # 如果返回的是字符串（提示文字：老师不存在/不是班主任）
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    # 返回统一响应模型到前端
    return ResponseBase(data=data)


@router.get("/{teacher_id}/teach_classes", response_model=ResponseBase)
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    # 调用dao.查询讲师所教的班
    data = dao.get_teach_classes(db, teacher_id)
    # 判断是否是提示文字
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    # 返回统一响应模型到前端
    return ResponseBase(data=data)


@router.get("/{teacher_id}/my_students", response_model=ResponseBase)
def get_my_students(teacher_id: int, db: Session = Depends(get_db)):
    # 调用dao.查询顾问所带的学生
    data = dao.get_my_students(db, teacher_id)
    # 判断是否是提示文字
    if isinstance(data, str):
        code = 404 if data == "老师不存在" else 400
        return ResponseBase(code=code, message=data, data=None)
    # 返回统一响应模型到前端
    return ResponseBase(data=data)
