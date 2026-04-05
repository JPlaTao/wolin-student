from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database import Base
from model.class_model import class_teacher

# 多对多连接class表需要的中间表
# class_teachers = Table(
#     'class_teacher',
#     Base.metadata,
#     Column('class_id', Integer, ForeignKey('class.class_id'), primary_key=True),
#     Column('teacher_id', Integer, ForeignKey('teacher.teacher_id'), primary_key=True)
# )


class Teacher(Base):
    __tablename__ = "teacher"# 表名
    teacher_id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_name = Column(String(30), comment="姓名")
    gender = Column(String(10), comment='男/女')
    phone = Column(String(20), comment='电话号码')
    role = Column(String(20), comment="角色：counselor顾问/headteacher班主任/lecturer讲师")
    is_deleted = Column(Boolean, default=False, comment="逻辑删除：0-未删除，1-已删除")

    # # 关联中间表(多对多)class.teacher()
    teach_classes = relationship('Class', secondary=class_teacher, back_populates='teachers')
    # # 关联班主任(一对多)
    class_as_head = relationship('Class', foreign_keys='Class.head_teacher_id', back_populates='head_teacher_info')
    # # 关联学生表(一对多)
    students = relationship('StuBasicInfo', foreign_keys='StuBasicInfo.advisor_id', back_populates='counselors')
