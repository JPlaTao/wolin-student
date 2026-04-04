from sqlalchemy.orm import Session
from model.teachers import Teacher
from schemas.teacher import TeacheresUpdata


# 新增老师

def create_teacher(db: Session, teacher: TeacheresUpdata):
    # 手动赋值，只传数据库有的字段，绝对不会错
    db_teacher = Teacher(
        teacher_name=teacher.teacher_name,
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
    for key, value in teacher.dict().items():
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
    return db_teacher


# ==========================================================
# 查询班主任管理的班级
def get_head_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    return teacher.head_classes if teacher else None


# 查询讲师教授的班级
def get_teach_classes(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    return teacher.teach_classes if teacher else None


# 查询顾问负责的学生
def get_my_students(db: Session, teacher_id: int):
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    return teacher.my_student if teacher else None
