from sqlalchemy import and_
from sqlalchemy.orm import Session
from model.student import StuBasicInfo
from schemas.student import StudentCreate


# 1、创建新学生记录（学生编号、学生班级、学生姓名、籍贯、毕业院校、专业、入学时间、毕业时间、学历、
# 顾问编号、年龄、性别）

# new_student_data 要声明类型
def create_student(new_student_data : StudentCreate,
                   db: Session):
    """创建新学生"""
    # 将传入的数据转换为数据库模型
    new_student = StuBasicInfo(
        stu_name=new_student_data.stu_name,
        class_id=new_student_data.class_id,
        native_place=new_student_data.native_place,
        graduated_school=new_student_data.graduated_school,
        major=new_student_data.major,
        admission_date=new_student_data.admission_date,
        graduation_date=new_student_data.graduation_date,
        education=new_student_data.education,
        advisor_id=new_student_data.advisor_id,
        age=new_student_data.age,
        gender=new_student_data.gender,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return {
        "stu_id": new_student.stu_id,
        "stu_name": new_student.stu_name,
        "class_id": new_student.class_id,
        "native_place": new_student.native_place,
        "graduated_school": new_student.graduated_school,
        "major": new_student.major,
        "admission_date": new_student.admission_date,
        "graduation_date": new_student.graduation_date,
        "education": new_student.education,
        "advisor_id": new_student.advisor_id,
        "age": new_student.age,
        "gender": new_student.gender,
        "is_deleted": new_student.is_deleted
    }


# 2、查询学生信息（支持按编号、姓名、班级等条件筛选）
def get_students(
        db: Session,
        stu_id: int = None,
        stu_name: str = None,
        class_id: int = None):
    # 默认全表扫描
    result = db.query(StuBasicInfo).filter(StuBasicInfo.is_deleted == False)

    #stu_id: 按学生编号查询
    if stu_id is not None:
        result = result.filter(StuBasicInfo.stu_id == stu_id)

    # stu_name: 按学生姓名查询
    if stu_name is not None:
        result = result.filter(StuBasicInfo.stu_name == stu_name)

    # class_id: 按班级编号查询
    if class_id is not None:
        result = result.filter(StuBasicInfo.class_id == class_id)

    students_temp = result.all()
    # 转换成字典
    students = [
        {
            "stu_id": i.stu_id,
            "stu_name": i.stu_name,
            "class_id": i.class_id,
            "native_place": i.native_place,
            "graduated_school": i.graduated_school,
            "major": i.major,
            "admission_date": i.admission_date,
            "graduation_date": i.graduation_date,
            "education": i.education,
            "advisor_id": i.advisor_id,
            "age": i.age,
            "gender": i.gender
        }
        for i in students_temp
    ]



    return students

# 更新学生信息
def update_student(db: Session, stu_id: int, update_data):
    # 查找未删除的学生
    result = db.query(StuBasicInfo).filter(
        and_(
        StuBasicInfo.is_deleted == False,
        StuBasicInfo.stu_id == stu_id)
    ).first()  # ← 加上 .first()


    if not result:
        return '不存在这个学生'
    else :
        if update_data.stu_name is not None:
            result.stu_name = update_data.stu_name
        if update_data.class_id is not None:
            result.class_id = update_data.class_id
        if update_data.native_place is not None:
            result.native_place = update_data.native_place
        if update_data.graduated_school is not None:
            result.graduated_school = update_data.graduated_school
        if update_data.major is not None:
            result.major = update_data.major
        if update_data.admission_date is not None:
            result.admission_date = update_data.admission_date
        if update_data.graduation_date is not None:
            result.graduation_date = update_data.graduation_date
        if update_data.education is not None:
            result.education = update_data.education
        if update_data.advisor_id is not None:
            result.advisor_id = update_data.advisor_id
        if update_data.age is not None:
            result.age = update_data.age
        if update_data.gender is not None:
            result.gender = update_data.gender

    db.commit()
    db.refresh(result)
    return '更新成功'


# 逻辑删除学生
def delete_student(db: Session, stu_id: int):
    # 查找未删除的学生
    result = db.query(StuBasicInfo).filter(
        and_(
        StuBasicInfo.is_deleted == False,
        StuBasicInfo.stu_id == stu_id)
    ).first()  # ← 加上 .first()


    if not result:
        return '不存在这个学生或已被删除'
    else :
        result.is_deleted = True

    db.commit()
    db.refresh(result)
    return '删除成功'
