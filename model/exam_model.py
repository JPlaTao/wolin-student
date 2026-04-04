from sqlalchemy import Column, Integer, Date, ForeignKey
from database import Base


class StuExamRecord(Base):
    __tablename__ = "stu_exam_record"
    # record_id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID（主键）")
    stu_id = Column(Integer, ForeignKey("stu_basic_info.stu_id"), primary_key=True, comment="学生编号")
    seq_no = Column(Integer, primary_key=True, comment="考核序次")
    grade = Column(Integer, default=0, comment="考核成绩")
    exam_date = Column(Date, default='1900-01-01', comment="考核日期")
    is_deleted = Column(Integer, default=0, comment="逻辑删除")