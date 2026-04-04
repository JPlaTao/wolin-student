from sqlalchemy.orm import Session
from model.class_model import Class
from schemas.class_schemas import ClassCreate, ClassUpdate


# ========================
# DAO：只做数据库操作
# ========================

# 查询所有班级
def get_all_class(db: Session):
    return db.query(Class).all()


# 根据ID查询单个班级
def get_class_by_id(db: Session, class_id: int):
    return db.query(Class).filter(Class.class_id == class_id).first()


# 创建班级
def create_class(db: Session, class_data: ClassCreate):
    # 把Pydantic数据转成数据库模型
    db_class = Class(
        class_name=class_data.class_name,
        start_time=class_data.start_time,
        head_teacher_id=class_data.head_teacher_id
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
def delete_class(db: Session, class_id: int):
    db_class = get_class_by_id(db, class_id)
    if not db_class:
        return False

    db.delete(db_class)
    db.commit()
    return True
