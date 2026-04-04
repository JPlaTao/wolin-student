from sqlalchemy.orm import Session
from model.employment import Employment

# 1. 根据学生ID查就业信息
def get_employment_by_stu_id(db: Session, stu_id: int):
    return db.query(Employment).filter(
        Employment.stu_id == stu_id,
        Employment.is_deleted == False
    ).first()

# 2. 根据班级ID查全班就业信息
def get_employment_by_class_id(db: Session, class_id: int):
    return db.query(Employment).filter(
        Employment.class_id == class_id,
        Employment.is_deleted == False
    ).all()

# 3. 更新就业信息
def update_employment(db: Session, employment: Employment, update_data):
    try:
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict.pop("stu_id", None)  # 禁止修改学生ID
        update_dict.pop("class_id", None)# 禁止修改班级ID
        for key, value in update_dict.items():
            if hasattr(employment, key):
                setattr(employment, key, value)
        db.commit()
        db.refresh(employment)
        return employment
    except Exception:
        db.rollback()
        print("更新失败")
        return False

# 4. 逻辑删除就业信息
def delete_employment(db: Session, employment: Employment):
    try:
        employment.is_deleted = True
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False

# 5. 创建空就业记录（学生模块调用）
def create_empty_employment(db: Session, stu_id: int, stu_name: str, class_id: int):
    emp = Employment(
        stu_id=stu_id,
        stu_name=stu_name,
        class_id=class_id,
        open_time=None,
        offer_time=None,
        company=None,
        salary=None,
        is_deleted=False
    )
    db.add(emp)
    return emp
# 6.根据emp_id查单条（删除用）
def get_employment_by_emp_id(db: Session, emp_id: int):
    return db.query(Employment).filter(
        Employment.emp_id == emp_id,
        Employment.is_deleted == False
    ).first()

# 恢复就业信息（取消逻辑删除）
# ================================
def restore_employment(db: Session, emp_id: int):
    # 找到这条记录（不管是否删除）
    emp = db.query(Employment).filter(Employment.emp_id == emp_id).first()
    if not emp:
        return False
    try:
        emp.is_deleted = False  # 恢复
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False