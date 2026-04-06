from sqlalchemy.orm import Session####
from model.teachers import Teacher
from schemas.teacher import TeacheresUpdata


# 新增老师的功能
def create_teacher(db: Session, teacher: TeacheresUpdata):
    # 创建一个变量对象, 把前端数据赋值进去
    db_teacher = Teacher(
        teacher_name=teacher.teacher_name,
        gender=teacher.gender,
        phone=teacher.phone,
        role=teacher.role,
        is_deleted=False  # 固定值，和你数据库一致
    )
    db.add(db_teacher)       # 加载到数据库会话
    db.commit()              # 提交到数据库
    db.refresh(db_teacher)   # 刷新==========
    return {
        "teacher_id": db_teacher.teacher_id,
        "teacher_name": db_teacher.teacher_name,
        "gender": db_teacher.gender,
        "phone": db_teacher.phone,
        "role": db_teacher.role
    }   # 把新增成功的老师数据变成字典的形式返回


# 查询单个老师
def get_teacher(db: Session, teacher_id: int):
    # 查询和匹配teacher_id
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 如果老师不存在
    if not teacher:
        return None
    return {
        "teacher_id": teacher.teacher_id,
        "teacher_name": teacher.teacher_name,
        "gender": teacher.gender,
        "phone": teacher.phone,
        "role": teacher.role
    }# 返回老师字典信息


# 查询所有未删除的老师
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
    ] # 遍历拿到每个老师的数据重新赋值转换成列表嵌套字典,通过api返回到前端


# 修改老师
def update_teacher(db: Session, teacher_id: int, teacher: TeacheresUpdata):
    # 找到要修改的老师
    db_teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 没找到
    if not db_teacher:
        return None
    # 把前端传过来的数据, 更新到数据库对象里
    for key, value in teacher.model_dump(exclude_unset=True).items():
        setattr(db_teacher, key, value)
    db.commit()             # 提交保存修改
    db.refresh(db_teacher)  # 刷新数据
    return {
        "teacher_id": db_teacher.teacher_id,
        "teacher_name": db_teacher.teacher_name,
        "gender": db_teacher.gender,
        "phone": db_teacher.phone,
        "role": db_teacher.role
    }# 返回老师字典信息


# 删除老师（逻辑删除，不是真删）
def delete_teacher(db: Session, teacher_id: int):
    # 找到要删除的老师
    db_teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    if db_teacher:
        db_teacher.is_deleted = True
        db.commit()  # 提交保存
        return True  # 删除成功
    return False  # 不存在


# ==========================================================
# 查询班主任管理的班级
def get_head_classes(db: Session, teacher_id: int):
    # 先查老师
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 如果老师不存在
    if not teacher:
        return "老师不存在"
    # 如果老师不是班主任
    if not teacher.class_as_head:
        return "该老师不是班主任"
    # 是班主任所带的班级
    return [
        {
            "class_id": c.class_id,
            "class_name": c.class_name,
            "head_teacher_id": c.head_teacher_id,
            "haed_teacher_name": teacher.teacher_name
        } for c in teacher.class_as_head
    ]


# 查询讲师教授的班级
def get_teach_classes(db: Session, teacher_id: int):
    # 查看老师
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 如果老师不存在
    if not teacher:
        return "老师不存在"
    # 如果老师不是讲师
    if teacher.role != "lecturer":
        return "该老师不是讲师"

    # 是讲师拿到他所教的班级
    return [
        {
            "class_id": c.class_id,
            "class_name": c.class_name,
            "head_teacher_id": teacher.teacher_id,
            "teacher_name": teacher.teacher_name
        } for c in teacher.teach_classes
    ]


# 查询顾问负责的学生
def get_my_students(db: Session, teacher_id: int):
    # 查询老师
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id, Teacher.is_deleted == False).first()
    # 如果老师不存在
    if not teacher:
        return "老师不存在"
    # 老师不是顾问
    if teacher.role != "counselor":
        return "该老师不是顾问，无负责的学生"
    # 是顾问但无学生
    if not teacher.students:
        return "该顾问暂无负责的学生"
     # 有学生
    return [
        {
            "stu_id": s.stu_id,
            "stu_name": s.stu_name,
            "class_id": s.class_id,
            "counselor_name": teacher.teacher_name
        } for s in teacher.students
    ]
