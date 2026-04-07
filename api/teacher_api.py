from fastapi import APIRouter, Depends, Query, HTTPException
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
@router.post("/", response_model=ResponseBase, summary="新增老师")
def create_teacher(teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    # 接收前端传的老师数据（自动校验格式） 自动获取数据库连接（Session）
    allowed_roles = ["counselor", "headteacher", "lecturer"]

    # 如果传了 role 且不在允许列表里 → 直接抛错，停止执行
    if teacher.role is not None and teacher.role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="角色不合法！只能是 counselor / headteacher / lecturer"
        )
    # 调用dao层,把数据存入数据库
    data = dao.create_teacher(db, teacher)
    # 返回统一响应模型到前端
    return ResponseBase(
        data=data
    )


# 查询单个老师
@router.get("/single", response_model=ResponseBase, summary="查询老师")
def get_teacher(
        db: Session = Depends(get_db),
        teacher_id: int = Query(None, description="按老师编号查询"),
        teacher_name: str = Query(None, description="按老师姓名查询"),
):
    # 调用老师查询
    teacher = dao.get_teacher(
        db,
        teacher_id=teacher_id,
        teacher_name=teacher_name
    )
    # 查不到
    if not teacher:
        raise HTTPException(status_code=404, detail="老师不存在")
    # 查到 → 正常返回
    return ResponseBase(data=teacher)


# 查询所有老师
@router.get("/all", response_model=ListResponse, summary="查询所有老师")
def get_all_teachers(db: Session = Depends(get_db)):
    # 调用 DAO，获取所有老师列表
    data = dao.get_all_teachers(db)
    # 返回带总数的统一响应格式（列表+total）
    return ListResponse(
        data=data,
        total=len(data)
    )


# 修改老师
@router.put("/{teacher_id}", response_model=ResponseBase, summary="修改老师信息")
def update_teacher(teacher_id: int, teacher: TeacheresUpdata, db: Session = Depends(get_db)):
    # 调用 dao修改老师数据
    data = dao.update_teacher(db, teacher_id, teacher)
    # 没查到
    if not data:
        raise HTTPException(status_code=404, detail="老师不存在")
    # 查到了
    return ResponseBase(
        data=data
    )


# 删除老师（逻辑删除）
@router.delete("/{teacher_id}", response_model=ResponseBase, summary="删除老师")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    # 调用 dao 删除（标记 is_deleted=True）
    success = dao.delete_teacher(db, teacher_id)
    # 如果老师不存在
    if not success:
        raise HTTPException(status_code=404, detail="老师不存在或者已删除")
    # 删除成功
    return ResponseBase(
        message="删除成功",
        data=None
    )


# 讲师绑定班级
@router.post("/bind-class", response_model=ResponseBase, summary="讲师绑定班级")
def bind_teacher_class(
        teacher_id: int = Query(..., description="讲师ID（必须传）"),
        class_ids: str = Query(..., description="班级ID列表，多个用英文逗号分隔，比如1,2,3"),
        db: Session = Depends(get_db)
):
    # 把前端传的字符串转成整数列表（比如 "1,2,3" → [1,2,3]）
    try:
        class_ids_list = [int(cid) for cid in class_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="班级ID必须是数字，多个用英文逗号分隔")

    # 调用DAO层绑定逻辑
    teacher = dao.bind_teacher_to_class(db, teacher_id, class_ids_list)
    if not teacher:
        raise HTTPException(status_code=400, detail="绑定失败：讲师不存在/不是讲师/班级不存在")

    # 返回成功响应
    return ResponseBase(
        code=200,
        message=f"讲师【{teacher.teacher_name}】绑定班级成功！",
        data={"teacher_id": teacher_id, "bind_class_ids": class_ids_list}
    )


# 讲师解绑班级
@router.delete("/{teacher_id}/unbind-class/{class_id}", response_model=ResponseBase, summary="解除讲师-班级绑定")
def unbind_teacher_class(
        teacher_id: int,
        class_id: int,
        db: Session = Depends(get_db)
):
    success = dao.unbind_teacher_from_class(db, teacher_id, class_id)
    # 返回是False
    if not success:
        raise HTTPException(status_code=400, detail="解除失败：讲师/班级不存在或未绑定")
    # 返回是True
    return ResponseBase(message="解除绑定成功")


# ========================================================
@router.get("/{teacher_id}/head_classes", response_model=ResponseBase, summary="查班主任所带的班级")
def get_head_classes(teacher_id: int, db: Session = Depends(get_db)):
    # 调用 dao. 查询班主任所带的班
    data = dao.get_head_classes(db, teacher_id)
    if isinstance(data, str):
        if data == "老师不存在":
            raise HTTPException(status_code=404, detail=data)
        else:
            raise HTTPException(status_code=400, detail=data)
    # 返回统一的响应模型到前端
    return ResponseBase(data=data)


@router.get("/{teacher_id}/teach_classes", response_model=ResponseBase, summary="查讲师所教的班级")
def get_teach_classes(teacher_id: int, db: Session = Depends(get_db)):
    # 调用dao.查询讲师所教的班
    data = dao.get_teach_classes(db, teacher_id)
    # 判断
    if isinstance(data, str):
        if data == "老师不存在":
            raise HTTPException(status_code=404, detail=data)
        else:
            raise HTTPException(status_code=400, detail=data)
    # 返回统一的响应模型到前端
    return ResponseBase(data=data)


@router.get("/{teacher_id}/my_students", response_model=ResponseBase, summary="查顾问带的学生")
def get_my_students(teacher_id: int, db: Session = Depends(get_db)):
    # 调用dao.查询顾问所带的学生
    data = dao.get_my_students(db, teacher_id)
    # 判断
    if isinstance(data, str):
        if data == "老师不存在":
            raise HTTPException(status_code=404, detail=data)
        else:
            raise HTTPException(status_code=400, detail=data)
    # 返回统一的响应模型到前端
    return ResponseBase(data=data)
