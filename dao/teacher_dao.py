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
    return {
        "teacher_id": db_teacher.teacher_id,
        "teacher_name": db_teacher.teacher_name,
        "gender": db_teacher.gender,
        "phone": db_teacher.phone,
        "role": db_teacher.role
    }


# 查询单个老师
def get_teacher(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        return None
    return {
        "teacher_id": teacher.teacher_id,
        "teacher_name": teacher.teacher_name,
        "gender": teacher.gender,
        "phone": teacher.phone,
        "role": teacher.role
    }


# 查询所有老师
def get_all_teachers(db: Session):
    data = db.query(Teacher).filter(Teacher.is_deleted == False).all()
    return [
        {
            "teacher_id": i.teacher_id,
            "teacher_name": i.teacher_name,
            "phone": i.phone,
            "role": i.role,
            "gender": i.gender
        } for i in data
    ]


# 修改老师
def update_teacher(db: Session, teacher_id: int, teacher: TeacheresUpdata):
    db_teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not db_teacher:
        return None
    for key, value in teacher.model_dump(exclude_unset=True).items():
        setattr(db_teacher, key, value)
    db.commit()
    db.refresh(db_teacher)
    return {
        "teacher_id": db_teacher.teacher_id,
        "teacher_name": db_teacher.teacher_name,
        "gender": db_teacher.gender,
        "phone": db_teacher.phone,
        "role": db_teacher.role
    }


# 删除老师
def delete_teacher(db: Session, teacher_id: int):
    db_teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if db_teacher:
        db_teacher.is_deleted = True
        db.commit()
        return True  # 删除成功
    return False  # 不存在


# ==========================================================
# 查询班主任管理的班级
def get_head_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        return "老师不存在"
    if not teacher.class_as_head:
        return "该老师不是班主任"
    return [
        {
            "class_id": c.class_id,
            "class_name": c.class_name,
            "head_teacher_id": c.head_teacher_id
        } for c in teacher.class_as_head
    ]


# 查询讲师教授的班级
def get_teach_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 2. 老师不存在 → 返回提示
    if not teacher:
        return "老师不存在"

    # 3. 老师不是讲师 → 返回提示
    if teacher.role != "lecturer":
        return "该老师不是讲师"

    # 4. 是讲师 → 返回班级字典列表
    return [
        {
            "class_id": c.class_id,
            "class_name": c.class_name,
            "head_teacher_id": c.head_teacher_id
        } for c in teacher.teach_classes
    ]


# 查询顾问负责的学生
def get_my_students(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if not teacher:
        return "老师不存在"
        # 2. 老师不是顾问 → 返回提示（假设顾问角色是 "advisor"，你可根据实际改）
    if teacher.role != "counselor":
        return "该老师不是顾问，无负责的学生"
        # 3. 是顾问但无学生 → 返回提示
    if not teacher.students:
        return "该顾问暂无负责的学生"
        # 4. 有学生 → 返回字典列表
    return [
        {
            "stu_id": s.stu_id,
            "stu_name": s.stu_name,
            "class_id": s.class_id
        } for s in teacher.students
    ]
