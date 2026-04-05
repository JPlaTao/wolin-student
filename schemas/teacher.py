from pydantic import BaseModel, Field

# ===================== 基础教师数据模型 =====================
class TeacherBase(BaseModel):
    teacher_id: int
    teacher_name: str
    gender: str
    phone: str
    role: str

    # 配置项：允许这个模型 从 SQLAlchemy 数据库对象 直接转换
    class Config:
        from_attributes = True

# 响应模型
class TeacheresUpdata(BaseModel):
    teacher_name: str = Field(..., description="老师姓名")
    gender: str = Field(..., description="性别：男/女")
    phone: str = Field(..., description="11位手机号")
    role: str = Field(..., description="角色：counselor/headteacher/lecturer")
