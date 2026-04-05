from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, desc, asc, extract, distinct
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from database import get_db
from model.student import StuBasicInfo
from model.class_model import Class
from model.exam_model import StuExamRecord
from model.employment import Employment
from model.teachers import Teacher

router = APIRouter(tags=["统计分析模块"], prefix="/statistics")


# ===================== 2.6.1 基本信息统计 =====================

@router.get("/students/over30", summary="查询所有超过30岁的学员信息")
def get_students_over_30(db: Session = Depends(get_db)):
    """返回年龄>30的学生（年龄为静态字段）"""
    students = db.query(
        StuBasicInfo.stu_id,
        StuBasicInfo.stu_name,
        StuBasicInfo.age,
        StuBasicInfo.gender,
        Class.class_name
    ).join(Class, StuBasicInfo.class_id == Class.class_id) \
        .filter(
        StuBasicInfo.is_deleted == False,
        Class.is_deleted == False,
        StuBasicInfo.age > 30
    ).all()

    result = [
        {
            "stu_id": s.stu_id,
            "stu_name": s.stu_name,
            "age": s.age,
            "gender": s.gender,
            "class_name": s.class_name
        }
        for s in students
    ]
    return {"code": 200, "count": len(result), "data": result}


@router.get("/classes/gender-stat", summary="统计每个班级的人数和男女生人数")
def class_gender_statistics(db: Session = Depends(get_db)):
    """返回每个班级的总人数、男生数、女生数"""
    stats = db.query(
        Class.class_id,
        Class.class_name,
        func.count(StuBasicInfo.stu_id).label("total"),
        func.sum(case((StuBasicInfo.gender == "男", 1), else_=0)).label("male"),
        func.sum(case((StuBasicInfo.gender == "女", 1), else_=0)).label("female")
    ).join(StuBasicInfo, StuBasicInfo.class_id == Class.class_id) \
        .filter(
        Class.is_deleted == False,
        StuBasicInfo.is_deleted == False
    ).group_by(Class.class_id, Class.class_name) \
        .all()

    result = [
        {
            "class_id": c.class_id,
            "class_name": c.class_name,
            "total": c.total,
            "male": c.male,
            "female": c.female
        }
        for c in stats
    ]
    return {"code": 200, "data": result}


# ===================== 2.6.2 成绩统计 =====================

@router.get("/score/always-above-80", summary="每次考试成绩都在80分以上的学生")
def students_always_above_80(db: Session = Depends(get_db)):
    """
    查询所有考试（所有seq_no）成绩均 >= 80 的学生。
    返回学生编号、姓名以及每次考试的成绩列表。
    """
    # 方法：找出存在任何一次成绩 < 80 的学生，然后排除
    subquery = db.query(StuExamRecord.stu_id).filter(
        StuExamRecord.grade < 80,
        StuExamRecord.is_deleted == 0
    ).distinct().subquery()

    good_students = db.query(StuBasicInfo).filter(
        StuBasicInfo.is_deleted == False,
        StuBasicInfo.stu_id.notin_(subquery)
    ).all()

    result = []
    for stu in good_students:
        # 获取该学生所有有效成绩
        exams = db.query(StuExamRecord).filter(
            StuExamRecord.stu_id == stu.stu_id,
            StuExamRecord.is_deleted == 0
        ).order_by(StuExamRecord.seq_no).all()
        result.append({
            "stu_id": stu.stu_id,
            "stu_name": stu.stu_name,
            "grades": [{"seq_no": e.seq_no, "grade": e.grade, "exam_date": e.exam_date} for e in exams]
        })

    return {"code": 200, "count": len(result), "data": result}


@router.get("/score/twice-failed", summary="有两次以上不及格的学生")
def students_twice_failed(db: Session = Depends(get_db)):
    """
    查询不及格次数 >= 2 的学生，返回姓名、班级、不及格成绩列表。
    """
    # 先找出不及格次数 >= 2 的学生ID
    fail_counts = db.query(
        StuExamRecord.stu_id,
        func.count(StuExamRecord.seq_no).label("fail_count")
    ).filter(
        StuExamRecord.grade < 60,
        StuExamRecord.is_deleted == 0
    ).group_by(StuExamRecord.stu_id) \
        .having(func.count(StuExamRecord.seq_no) >= 2) \
        .subquery()

    result = db.query(
        StuBasicInfo.stu_id,
        StuBasicInfo.stu_name,
        Class.class_name,
        StuExamRecord.seq_no,
        StuExamRecord.grade,
        StuExamRecord.exam_date
    ).join(fail_counts, StuBasicInfo.stu_id == fail_counts.c.stu_id) \
        .join(Class, StuBasicInfo.class_id == Class.class_id) \
        .join(StuExamRecord, StuBasicInfo.stu_id == StuExamRecord.stu_id) \
        .filter(
        StuExamRecord.grade < 60,
        StuExamRecord.is_deleted == 0,
        StuBasicInfo.is_deleted == False,
        Class.is_deleted == False
    ).order_by(StuBasicInfo.stu_id, StuExamRecord.seq_no) \
        .all()

    # 组装结果：按学生分组
    from collections import defaultdict
    grouped = defaultdict(lambda: {"stu_name": "", "class_name": "", "failed_exams": []})
    for row in result:
        key = row.stu_id
        grouped[key]["stu_name"] = row.stu_name
        grouped[key]["class_name"] = row.class_name
        grouped[key]["failed_exams"].append({
            "seq_no": row.seq_no,
            "grade": row.grade,
            "exam_date": row.exam_date
        })

    final = [
        {
            "stu_id": sid,
            "stu_name": info["stu_name"],
            "class_name": info["class_name"],
            "failed_count": len(info["failed_exams"]),
            "failed_exams": info["failed_exams"]
        }
        for sid, info in grouped.items()
    ]
    return {"code": 200, "count": len(final), "data": final}


@router.get("/score/class-avg-per-exam", summary="每次考试每个班级的平均分（从高到低）")
def class_avg_per_exam(db: Session = Depends(get_db)):
    """
    统计每次考试（seq_no）每个班级的平均分，按考试序号分组，组内按平均分降序。
    """
    # 先获取所有存在的考试序号
    seq_nos = db.query(distinct(StuExamRecord.seq_no)).filter(
        StuExamRecord.is_deleted == 0
    ).order_by(StuExamRecord.seq_no).all()
    seq_nos = [s[0] for s in seq_nos]

    result_by_seq = {}
    for seq in seq_nos:
        avg_scores = db.query(
            Class.class_id,
            Class.class_name,
            func.avg(StuExamRecord.grade).label("avg_grade")
        ).join(StuBasicInfo, StuBasicInfo.class_id == Class.class_id) \
            .join(StuExamRecord, StuExamRecord.stu_id == StuBasicInfo.stu_id) \
            .filter(
            StuExamRecord.seq_no == seq,
            StuExamRecord.is_deleted == 0,
            StuBasicInfo.is_deleted == False,
            Class.is_deleted == False
        ).group_by(Class.class_id, Class.class_name) \
            .order_by(desc("avg_grade")) \
            .all()

        result_by_seq[f"第{seq}次考试"] = [
            {"class_name": row.class_name, "avg_grade": round(row.avg_grade, 2)}
            for row in avg_scores
        ]

    return {"code": 200, "data": result_by_seq}


# ===================== 2.6.3 就业统计 =====================

@router.get("/employment/top5-salary", summary="就业薪资最高的前五名学生")
def top5_salary_students(db: Session = Depends(get_db)):
    """返回薪资最高的5名学生，包含姓名、班级、就业时间、公司"""
    top5 = db.query(
        Employment.stu_id,
        Employment.stu_name,
        Employment.company,
        Employment.salary,
        Employment.offer_time,
        Class.class_name
    ).join(Class, Employment.class_id == Class.class_id) \
        .filter(
        Employment.is_deleted == False,
        Employment.salary.isnot(None),
        Class.is_deleted == False
    ).order_by(desc(Employment.salary)) \
        .limit(5) \
        .all()

    result = [
        {
            "stu_name": row.stu_name,
            "class_name": row.class_name,
            "salary": row.salary,
            "offer_time": row.offer_time,
            "company": row.company
        }
        for row in top5
    ]
    return {"code": 200, "data": result}


@router.get("/employment/duration-per-student", summary="每个学生的就业时长（天）")
def employment_duration_per_student(db: Session = Depends(get_db)):
    """
    计算每个学生的就业时长 = offer_time - open_time（天数）。
    只计算两个时间均有的学生。
    """
    records = db.query(
        Employment.stu_id,
        Employment.stu_name,
        Employment.open_time,
        Employment.offer_time
    ).filter(
        Employment.is_deleted == False,
        Employment.open_time.isnot(None),
        Employment.offer_time.isnot(None)
    ).all()

    result = []
    for rec in records:
        delta = (rec.offer_time - rec.open_time).days
        result.append({
            "stu_id": rec.stu_id,
            "stu_name": rec.stu_name,
            "open_time": rec.open_time,
            "offer_time": rec.offer_time,
            "duration_days": delta
        })
    return {"code": 200, "data": result}


@router.get("/employment/avg-duration-per-class", summary="每个班级的平均就业时长（仅统计有就业开放时间的学生）")
def avg_duration_per_class(db: Session = Depends(get_db)):
    """
    统计每个班级的平均就业时长（天数），只计算有open_time的学生。
    """
    stats = db.query(
        Class.class_id,
        Class.class_name,
        func.avg(func.datediff(Employment.offer_time, Employment.open_time)).label("avg_days")
    ).join(Employment, Employment.class_id == Class.class_id) \
        .filter(
        Class.is_deleted == False,
        Employment.is_deleted == False,
        Employment.open_time.isnot(None),
        Employment.offer_time.isnot(None)
    ).group_by(Class.class_id, Class.class_name) \
        .all()

    result = [
        {
            "class_name": row.class_name,
            "avg_duration_days": round(row.avg_days, 1) if row.avg_days else None
        }
        for row in stats
    ]
    return {"code": 200, "data": result}


# ===================== 额外复杂统计（多表联查） =====================

@router.get("/advanced/class-avg-score-rank", summary="各班平均成绩排名（含班主任姓名）")
def class_avg_score_rank(db: Session = Depends(get_db)):
    """
    统计每个班级所有学生所有有效考试的平均分，按平均分从高到低排名，
    并显示班主任姓名（多表联查：班级、学生、成绩、教师）。
    """
    rank = db.query(
        Class.class_id,
        Class.class_name,
        Teacher.teacher_name.label("head_teacher"),
        func.avg(StuExamRecord.grade).label("avg_score")
    ).join(Teacher, Class.head_teacher_id == Teacher.teacher_id) \
        .join(StuBasicInfo, StuBasicInfo.class_id == Class.class_id) \
        .join(StuExamRecord, StuExamRecord.stu_id == StuBasicInfo.stu_id) \
        .filter(
        Class.is_deleted == False,
        Teacher.is_deleted == False,
        StuBasicInfo.is_deleted == False,
        StuExamRecord.is_deleted == 0
    ).group_by(Class.class_id, Class.class_name, Teacher.teacher_name) \
        .order_by(desc("avg_score")) \
        .all()

    result = [
        {
            "rank": idx + 1,
            "class_name": row.class_name,
            "head_teacher": row.head_teacher,
            "avg_score": round(row.avg_score, 2)
        }
        for idx, row in enumerate(rank)
    ]
    return {"code": 200, "data": result}


@router.get("/advanced/salary-distribution", summary="各薪资区间学生人数统计")
def salary_distribution(db: Session = Depends(get_db)):
    """
    按薪资区间统计就业学生人数，区间：<5k, 5k-8k, 8k-12k, 12k-20k, >20k。
    """
    bins = [
        (0, 5000, "<5k"),
        (5000, 8000, "5k-8k"),
        (8000, 12000, "8k-12k"),
        (12000, 20000, "12k-20k"),
        (20000, float('inf'), ">20k")
    ]
    result = []
    for low, high, label in bins:
        count = db.query(func.count(Employment.emp_id)).filter(
            Employment.is_deleted == False,
            Employment.salary >= low,
            Employment.salary < high if high != float('inf') else Employment.salary >= low
        ).scalar()
        result.append({"range": label, "count": count})
    return {"code": 200, "data": result}


@router.get("/advanced/most-improved-students", summary="成绩进步最快的学生（最后一次考试减第一次考试）")
def most_improved_students(limit: int = 5, db: Session = Depends(get_db)):
    """
    计算每个学生第一次考试和最后一次考试的成绩差，按进步分数降序排列。
    需要每个学生至少有2次有效考试。
    """
    # 获取每个学生的最小和最大seq_no对应的成绩
    # 使用窗口函数或子查询。SQLAlchemy中可以使用标量子查询。
    subq_first = db.query(
        StuExamRecord.stu_id,
        StuExamRecord.grade.label("first_grade"),
        StuExamRecord.seq_no.label("first_seq")
    ).filter(StuExamRecord.is_deleted == 0).distinct().subquery()
    # 更简单的方法：使用group by + min/max seq_no，然后关联两次
    # 但需要分别取第一次和最后一次的成绩。这里采用两次子查询。
    first_grades = db.query(
        StuExamRecord.stu_id,
        StuExamRecord.grade.label("first_grade")
    ).filter(
        StuExamRecord.is_deleted == 0,
        StuExamRecord.seq_no == db.query(func.min(StuExamRecord.seq_no))
        .filter(StuExamRecord.stu_id == StuBasicInfo.stu_id, StuExamRecord.is_deleted == 0)
        .correlate(StuBasicInfo).as_scalar()
    ).subquery()

    last_grades = db.query(
        StuExamRecord.stu_id,
        StuExamRecord.grade.label("last_grade")
    ).filter(
        StuExamRecord.is_deleted == 0,
        StuExamRecord.seq_no == db.query(func.max(StuExamRecord.seq_no))
        .filter(StuExamRecord.stu_id == StuBasicInfo.stu_id, StuExamRecord.is_deleted == 0)
        .correlate(StuBasicInfo).as_scalar()
    ).subquery()

    # 但是上面的correlate写法在FastAPI中可能复杂，我们改用更直接的方式：先获取每个学生的min_seq和max_seq，然后join两次。
    # 为了避免过于复杂，我使用原生SQL思想，但用SQLAlchemy ORM方式实现。
    # 另一种简单方法：循环遍历，但效率低。这里采用两次子查询且不使用correlate，直接关联。
    # 实际生产中建议使用窗口函数，但这里为了可读性，使用两次标量子查询（在filter中）。

    # 重新实现：使用distinct on? 不，改用group by + min/max 然后self-join。
    min_max = db.query(
        StuExamRecord.stu_id,
        func.min(StuExamRecord.seq_no).label("min_seq"),
        func.max(StuExamRecord.seq_no).label("max_seq")
    ).filter(StuExamRecord.is_deleted == 0).group_by(StuExamRecord.stu_id).subquery()

    first = db.query(
        StuExamRecord.stu_id,
        StuExamRecord.grade.label("first_grade")
    ).join(min_max, and_(
        StuExamRecord.stu_id == min_max.c.stu_id,
        StuExamRecord.seq_no == min_max.c.min_seq
    )).subquery()

    last = db.query(
        StuExamRecord.stu_id,
        StuExamRecord.grade.label("last_grade")
    ).join(min_max, and_(
        StuExamRecord.stu_id == min_max.c.stu_id,
        StuExamRecord.seq_no == min_max.c.max_seq
    )).subquery()

    improved = db.query(
        StuBasicInfo.stu_id,
        StuBasicInfo.stu_name,
        Class.class_name,
        first.c.first_grade,
        last.c.last_grade,
        (last.c.last_grade - first.c.first_grade).label("improvement")
    ).select_from(StuBasicInfo) \
        .join(Class, StuBasicInfo.class_id == Class.class_id) \
        .join(first, StuBasicInfo.stu_id == first.c.stu_id) \
        .join(last, StuBasicInfo.stu_id == last.c.stu_id) \
        .filter(
        StuBasicInfo.is_deleted == False,
        Class.is_deleted == False,
        first.c.first_grade.isnot(None),
        last.c.last_grade.isnot(None),
        StuBasicInfo.stu_id.in_(db.query(min_max.c.stu_id).filter(min_max.c.min_seq != min_max.c.max_seq))
    ).order_by(desc("improvement")) \
        .limit(limit) \
        .all()

    result = [
        {
            "stu_name": row.stu_name,
            "class_name": row.class_name,
            "first_grade": row.first_grade,
            "last_grade": row.last_grade,
            "improvement": row.improvement
        }
        for row in improved
    ]
    return {"code": 200, "data": result}


@router.get("/advanced/class-employment-rate", summary="各班级就业率（有就业记录且薪资不为空的学生占比）")
def class_employment_rate(db: Session = Depends(get_db)):
    """
    统计每个班级的就业率：有就业记录（Employment.is_deleted=False）且薪资不为空的学生数 / 班级总学生数。
    """
    total_students = db.query(
        Class.class_id,
        Class.class_name,
        func.count(StuBasicInfo.stu_id).label("total")
    ).join(StuBasicInfo, StuBasicInfo.class_id == Class.class_id) \
        .filter(Class.is_deleted == False, StuBasicInfo.is_deleted == False) \
        .group_by(Class.class_id, Class.class_name).subquery()

    employed_students = db.query(
        Employment.class_id,
        func.count(distinct(Employment.stu_id)).label("employed")
    ).filter(
        Employment.is_deleted == False,
        Employment.salary.isnot(None)
    ).group_by(Employment.class_id).subquery()

    result = db.query(
        total_students.c.class_id,
        total_students.c.class_name,
        total_students.c.total,
        func.coalesce(employed_students.c.employed, 0).label("employed"),
        (func.coalesce(employed_students.c.employed, 0) / total_students.c.total * 100).label("rate")
    ).outerjoin(employed_students, total_students.c.class_id == employed_students.c.class_id) \
        .all()

    final = [
        {
            "class_name": row.class_name,
            "total_students": row.total,
            "employed_students": row.employed,
            "employment_rate": round(row.rate, 2)
        }
        for row in result
    ]
    return {"code": 200, "data": final}

@router.get("/dashboard", summary="数据看板汇总")
def dashboard_stats(db: Session = Depends(get_db)):
    # 1. 学生总数
    total_students = db.query(StuBasicInfo).filter(StuBasicInfo.is_deleted == False).count()

    # 2. 班级总数
    total_classes = db.query(Class).filter(Class.is_deleted == False).count()

    # 3. 平均年龄（仅计算有年龄且未删除的学生）
    avg_age_result = db.query(func.avg(StuBasicInfo.age)).filter(StuBasicInfo.is_deleted == False).first()
    avg_age = round(avg_age_result[0], 1) if avg_age_result[0] else 0

    # 4. 就业率：有就业记录（is_deleted=False）且薪资不为空的学生数 / 总学生数
    employed = db.query(func.count(distinct(Employment.stu_id))).filter(
        Employment.is_deleted == False,
        Employment.salary.isnot(None)
    ).scalar() or 0
    employment_rate = round(employed / total_students * 100, 1) if total_students > 0 else 0

    # 5. 薪资前五名（关联班级获取班级名称）
    top_salary = db.query(
        Employment.stu_name,
        Class.class_name,
        Employment.salary,
        Employment.company
    ).join(Class, Employment.class_id == Class.class_id).filter(
        Employment.is_deleted == False,
        Employment.salary.isnot(None),
        Class.is_deleted == False
    ).order_by(Employment.salary.desc()).limit(5).all()

    top_salary_list = [
        {
            "stu_name": row.stu_name,
            "class_name": row.class_name,
            "salary": row.salary,
            "company": row.company
        }
        for row in top_salary
    ]

    return {
        "code": 200,
        "data": {
            "total_students": total_students,
            "total_classes": total_classes,
            "avg_age": avg_age,
            "employment_rate": employment_rate,
            "top_salary": top_salary_list
        }
    }