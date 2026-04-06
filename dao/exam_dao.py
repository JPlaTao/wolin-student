from sqlalchemy import and_
from sqlalchemy.orm import Session
from model.exam_model import StuExamRecord


# 按考核序次录⼊考核成绩（学⽣编号、考核序次、成绩）
def exam_submit( exam_data, db: Session ):
    # 若有被删除的数据 则更新数据并将is_deleted置为0
    _query = db.query(StuExamRecord).filter(
            and_(
                StuExamRecord.is_deleted == 1,
                StuExamRecord.stu_id == exam_data.stu_id,
                StuExamRecord.seq_no == exam_data.seq_no
            )
    )
    data = _query.first()
    if data:
        _query.update({
            StuExamRecord.is_deleted: 0,
            StuExamRecord.grade: exam_data.grade,
            StuExamRecord.exam_date: exam_data.exam_date
        })
        db.commit()
        return {
                "message": "success",
                "stu_id": exam_data.stu_id,
                "seq_no": exam_data.seq_no,
                "grade": exam_data.grade,
                "exam_date": exam_data.exam_date
        }
    # 无则新增数据
    else:
        try:
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
                "message": "success",
                "stu_id": submit.stu_id,
                "seq_no": submit.seq_no,
                "grade": submit.grade,
                "exam_date": submit.exam_date
            }
        # 捕获异常 如主键冲突/外键约束
        except Exception as e:
            pk_e = "duplicate entry"
            fk_e = "foreign key constraint fails"
            if pk_e in str(e).lower():
                return { "message": "提交失败：该学生的此次考核记录已存在，请勿重复提交。" }
            elif fk_e in str(e).lower():
                return { "message": "提交失败：该学生编号不存在，请先创建学生信息。" }
            else:
                return { "message": f"{e}" }


# 更新考试成绩
def exam_update( stu_id: int, seq_no: int, exam_data, db: Session ):
    # 基础查询 过滤学生id和考核序次
    _query = db.query(StuExamRecord).filter(
            and_(
                StuExamRecord.is_deleted == 0,
                StuExamRecord.stu_id == stu_id,
                StuExamRecord.seq_no == seq_no
            )
    )
    data = _query.first()
    # 若有数则更新 包括is_deleted=1的数据
    if data:
        cnt = _query.update({
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
