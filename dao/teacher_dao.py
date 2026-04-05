from sqlalchemy.orm import Session
from model.teachers import Teacher
from schemas.teacher import TeacheresUpdata


# 新增老师
def create_teacher(db: Session, teacher: TeacheresUpdata):
    # 手动赋值，只传数据库有的字段，绝对不会错
    db_teacher = Teacher(
        teacher_name=teacher.teacher_name,
        gender=teacher.gender,
        phone=teacher.phone,
        role=teacher.role,
        is_deleted=False  # 固定值，和你数据库一致
    )
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher


# 查询单个老师
def get_teacher(db: Session, teacher_id: int):
    return db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()


# 查询所有老师
def get_all_teachers(db: Session):
    return db.query(Teacher).filter(Teacher.is_deleted == False).all()


# 修改老师
def update_teacher(db: Session, teacher_id: int, teacher: TeacheresUpdata):
    db_teacher = get_teacher(db, teacher_id)
    if not db_teacher:
        return None
    for key, value in teacher.dict(exclude_unset=True).items():
        setattr(db_teacher, key, value)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher


# 删除老师
def delete_teacher(db: Session, teacher_id: int):
    db_teacher = get_teacher(db, teacher_id)
    if db_teacher:
        db_teacher.is_deleted = True
        db.commit()
        return {"msg": "删除成功"}  # 删除成功返回这个
    return {"msg": "老师不存在或已删除"}  # 不存在返回这个


# ==========================================================
# 查询班主任管理的班级
def get_head_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    return teacher.class_as_head if teacher else None


# 查询讲师教授的班级
def get_teach_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        return {"msg": "讲师不存在"}
    # 先判断角色，只有讲师才有授课班级
    if teacher.role != "lecturer":
        return {"msg": "该老师不是讲师，无授课班级"}
    # 如果没有授课班级
    if not teacher.teach_classes:
        return {"msg": "讲师暂无班级上课"}
    # 有班级就返回班级列表
    return teacher.teach_classes


# 查询顾问负责的学生
def get_my_students(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        return {"msg": "老师不存在"}

    # 有绑定学生 → 返回列表
    if teacher.students:
        return teacher.students

    # 没有 → 返回提示
    return {"msg": "该顾问暂无负责学生"}

