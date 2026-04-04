from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from database import Base

# 班级-教师 多对多中间表
class_teacher = Table(
    "class_teacher",
    Base.metadata,
    Column("class_id", Integer, ForeignKey("class.class_id"), primary_key=True, comment="班级ID"),
    Column("teacher_id", Integer, ForeignKey("teacher.teacher_id"), primary_key=True, comment="教师ID"),
    comment="班级教师多对多关联表"

)


class Class(Base):
    __tablename__ = "class"
    __table_args__ = {"comment": "班级信息表"}
    class_id = Column(Integer, primary_key=True, autoincrement=True, comment="班级编号")
    class_name = Column(String(50), nullable=False, comment="班级名称")
    start_time = Column(DateTime, nullable=False, comment="开课时间")
    is_deleted = Column(Boolean, default=False, nullable=False, comment="是否删除:0-未删除,1-已删除")
    # 关联关系OMR自动映射

    # 关系：一个班只有一个班主任(一对一)
    head_teacher_id = Column(Integer, ForeignKey("teacher.teacher_id"), nullable=True, comment="班主任ID")
    head_teacher_info = relationship("Teacher", back_populates="class_as_head", uselist=False)
    # 关系：一个班级对应多个教师（多对多）
    teachers = relationship("Teacher", secondary=class_teacher, back_populates="teach_classes")
    # 关系：一个班级对应多个学生（一对多）
    students = relationship("StuBasicInfo", back_populates="class_")

    def __repr__(self):
        return f"<Class(class_id={self.class_id}, name='{self.class_name}',head_teacher_id='{self.head_teacher_id}')>"
