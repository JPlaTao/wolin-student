from sqlalchemy import and_
from sqlalchemy.orm import Session
from model.student import StuBasicInfo
from schemas.student import StudentCreate


def format_student_data(students_query_result):
    """规范返回数据,主要目的是不展示is_deleted字段"""
    # 判断是否是列表（多条数据）
    if isinstance(students_query_result, list):
        # 多条数据：转换成列表套字典
        return [
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
            for i in students_query_result
        ]
    else:
        # 单条数据：转换成字典
        return {
            "stu_id": students_query_result.stu_id,
            "stu_name": students_query_result.stu_name,
            "class_id": students_query_result.class_id,
            "native_place": students_query_result.native_place,
            "graduated_school": students_query_result.graduated_school,
            "major": students_query_result.major,
            "admission_date": students_query_result.admission_date,
            "graduation_date": students_query_result.graduation_date,
            "education": students_query_result.education,
            "advisor_id": students_query_result.advisor_id,
            "age": students_query_result.age,
            "gender": students_query_result.gender
        }


def create_student(
        db: Session,
        new_student_data: StudentCreate
):
    """
    创建新学生记录（纯数据操作，不包含业务校验）
    """
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
    student = format_student_data(new_student)
    return student


def get_students(
        db: Session,
        stu_id: int = None,
        stu_name: str = None,
        class_id: int = None):
    """查询学生信息（支持按编号、姓名、班级等条件筛选）"""
    # 默认全表扫描
    result = db.query(StuBasicInfo).filter(StuBasicInfo.is_deleted == False)

    # stu_id: 按学生编号查询
    if stu_id is not None:
        result = result.filter(StuBasicInfo.stu_id == stu_id)

    # stu_name: 按学生姓名查询
    if stu_name is not None:
        result = result.filter(StuBasicInfo.stu_name == stu_name)

    # class_id: 按班级编号查询
    if class_id is not None:
        result = result.filter(StuBasicInfo.class_id == class_id)

    students_temp = result.all()
    students = format_student_data(students_temp)

    return students


def update_student(db: Session, stu_id: int, update_data):
    """更新学生信息（纯数据操作）"""
    # 查找未删除的学生
    result = db.query(StuBasicInfo).filter(
        and_(
            StuBasicInfo.is_deleted == False,
            StuBasicInfo.stu_id == stu_id)
    ).first()

    if not result:
        return False

    # 只更新传入的字段
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if hasattr(result, key):
            setattr(result, key, value)

    db.commit()
    db.refresh(result)
    student = format_student_data(result)
    return student


def delete_student(db: Session, stu_id: int):
    """逻辑删除学生"""
    # 查找未删除的学生
    result = db.query(StuBasicInfo).filter(
        and_(
            StuBasicInfo.is_deleted == False,
            StuBasicInfo.stu_id == stu_id)
    ).first()

    if not result:
        return '不存在这个学生或已被删除'

    result.is_deleted = True

    db.commit()
    db.refresh(result)
    return '删除成功'
