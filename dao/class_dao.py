from sqlalchemy.orm import Session
from model.class_model import Class, class_teacher
from schemas.class_schemas import ClassCreate, ClassUpdate


# ========================
# DAO：只做数据库操作
# ========================

# 查询所有班级
def get_all_class(db: Session, include_deleted: bool = False):  # 【修改】参数控制是否含已删除
    query = db.query(Class)
    if not include_deleted:
        query = query.filter(Class.is_deleted == False)
    return query.all()


# 根据ID查询单个班级
def get_class_by_id(db: Session, class_id: int, include_deleted: bool = False):  # [修改]参数控制
    query = db.query(Class).filter(Class.class_id == class_id)
    if not include_deleted:
        query = query.filter(Class.is_deleted == False)
    return query.first()


# 创建班级
def create_class(db: Session, class_data: ClassCreate):
    # 把Pydantic数据转成数据库模型
    db_class = Class(
        class_name=class_data.class_name,
        start_time=class_data.start_time,
        head_teacher_id=class_data.head_teacher_id,
        is_deleted=False  # 【新增】默认未删除
    )
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class


# 更新班级
def update_class(db: Session, class_id: int, class_data: ClassUpdate):
    db_class = get_class_by_id(db, class_id)
    if not db_class:
        return None

    # 只更新有传值的字段
    if class_data.class_name is not None:
        db_class.class_name = class_data.class_name
    if class_data.start_time is not None:
        db_class.start_time = class_data.start_time
    if class_data.head_teacher_id is not None:
        db_class.head_teacher_id = class_data.head_teacher_id

    db.commit()
    db.refresh(db_class)
    return db_class


# 删除班级
def delete_class(db: Session, class_id: int, hard_delete: bool = False):
    db_class = get_class_by_id(db, class_id)
    if not db_class:
        return False
    if hard_delete:
        db.execute(
            class_teacher.delete().where(class_teacher.c.class_id == class_id)
        )
        db.delete(db_class)
    else:
        db_class.is_deleted = True

        # 【修改】新增：手动删除中间表关联,只标记 is_deleted=True
    db.commit()
    return True


# 恢复软删除
def restore_class(db: Session, class_id: int):
    db_class = db.query(Class).filter(
        Class.class_id == class_id,
        Class.is_deleted == True
    ).first()

    if not db_class:
        return False

    db_class.is_deleted = False
    db.commit()
    db.refresh(db_class)
    return True
