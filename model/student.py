from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class StuBasicInfo(Base):
    __tablename__ = "stu_basic_info"
    stu_id = Column(Integer, primary_key=True, autoincrement=True)
    stu_name = Column(String(20), nullable=False)
    native_place = Column(String(50), nullable=False)
    graduated_school = Column(String(50), nullable=False)
    major = Column(String(50), nullable=False)
    admission_date = Column(DateTime, nullable=False)
    graduation_date = Column(DateTime, nullable=False)
    education = Column(String(20), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(2), nullable=False)
    is_deleted = Column(Integer, default=0, nullable=False)

    # 对应的顾问 外键指向老师表中的一个老师 一对一 一个学生对应一个顾问(销售)
    advisor_id = Column(Integer, ForeignKey("teacher.teacher_id"))
    # 顾问对应的关系
    counselor = relationship("Teacher", foreign_keys=[advisor_id], back_populates="students")

    # 学生所在的班级, 一对多 外键指向班级表中的一个班级
    class_id = Column(Integer, ForeignKey("class.class_id"), nullable=False)
    # 班级对应的关系
    class_ = relationship("Class", back_populates="students")

    class Config:
        from_attributes = True
