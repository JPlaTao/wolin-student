from sqlalchemy import and_
from sqlalchemy.orm import Session
from model.exam_model import StuExamRecord


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
    # 基础查询 过滤学生id和考核序次
    _query = db.query(StuExamRecord).filter(
        and_(
            StuExamRecord.stu_id == stu_id,
            StuExamRecord.seq_no == seq_no
        )
    )
    data = _query.first()
    # 若有数则更新
    if data:
        cnt = _query.update({
            StuExamRecord.is_deleted: 0,
            StuExamRecord.grade: exam_data.grade,
            StuExamRecord.exam_date: exam_data.exam_date
        })
        db.commit()
        return f"'{stu_id=}' & '{seq_no=}' -> {cnt} rows updated"
    else:
        return f"'{stu_id=}' & '{seq_no=}' not found"


# 删除考试成绩（逻辑删除）
def exam_delete(
        stu_id: int,
        seq_no: int | None,
        db: Session
):
    # 先构建基础查询(不执行)
    _query = db.query(StuExamRecord).filter(
        and_(
            StuExamRecord.is_deleted == 0,
            StuExamRecord.stu_id == stu_id
        )
    )
    # seq_no不为空时追加过滤条件
    if seq_no is not None:
        _query = _query.filter(StuExamRecord.seq_no == seq_no)
    # 更新逻辑删除字段并拿到更新数量
    cnt = _query.update({StuExamRecord.is_deleted: 1})
    db.commit()
    # 逻辑删除查询到的数据
    if cnt != 0:
        return f"'{stu_id=}' & '{seq_no=}' -> {cnt} rows deleted"
    else:
        return f"'{stu_id=}' & '{seq_no=}' not found"
