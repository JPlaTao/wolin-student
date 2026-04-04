from sqlalchemy import and_
from sqlalchemy.orm import Session
from model.exam_model import StuExamRecord
from typing import Optional


# 按考核序次录⼊考核成绩（学⽣编号、考核序次、成绩）
def exam_submit(
        exam_data,
        db: Session
):
    submit = StuExamRecord(
        stu_id = exam_data.stu_id,
        seq_no = exam_data.seq_no,
        grade = exam_data.grade,
        exam_date = exam_data.exam_date,
        is_deleted = 0
    )
    db.add(submit)
    db.commit()
    db.refresh(submit)
    return {
        "stu_id": submit.stu_id,
        "seq_no": submit.seq_no,
        "grade": submit.grade,
        "exam_date": submit.exam_date
    }


# 更新考试成绩
def exam_update(
        stu_id: int,
        seq_no: int,
        exam_data,
        db: Session
):
    # 查询学生id和考核序次是否存在
    _query = db.query(StuExamRecord).filter(
        and_(
            StuExamRecord.is_deleted == 0,
            StuExamRecord.stu_id == stu_id,
            StuExamRecord.seq_no == seq_no
        )
    ).first()

    # 更新数据 返回查询结果
    if not _query:
        return f"'{stu_id=}' & '{seq_no=}' not found"
    else:
        if exam_data.grade is not None:
            _query.grade = exam_data.grade
        if exam_data.exam_date is not None:
            _query.exam_date = exam_data.exam_date
    db.commit()
    db.refresh(_query)
    return f"'{stu_id=}' & '{seq_no=}' updated"


# 删除考试成绩（逻辑删除）
def exam_delete(
        stu_id: int,
        seq_no: int | None,
        db: Session
):
    # 取对应考试序次/所有考试序次的数据
    if seq_no is not None:
        _query = db.query(StuExamRecord).filter(
            and_(
                StuExamRecord.is_deleted == 0,
                StuExamRecord.stu_id == stu_id,
                StuExamRecord.seq_no == seq_no
            )
        ).all
    else:
        _query = db.query(StuExamRecord).filter(
            and_(
                StuExamRecord.is_deleted == 0,
                StuExamRecord.stu_id == stu_id
            )
        ).all
    # 逻辑删除查询到的数据
    if not _query:
        return f"'{stu_id=}' & '{seq_no=}' not found"
    else:
        _query.is_deleted = 1
        db.commit()
        db.refresh(_query)
        return f"'{stu_id=}' & '{seq_no=}' deleted"
