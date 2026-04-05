import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from api import (
    student_api,
    class_api,
    teacher_api,
    exam_api,
    employment_api,
    statistics_api,
    query_agent,
    auth_api      # 新增认证模块
)
from knowledge_base import build_knowledge_base
import model.user   # 确保 User 表被创建

# 创建所有表（包括 users）
Base.metadata.create_all(bind=engine)

# 构建知识库（如果模型存在则构建，否则跳过，不影响其他功能）
build_knowledge_base()

app = FastAPI(
    title="沃林学生管理系统",
    description="FastAPI + MySQL 学生信息/成绩/就业/统计管理",
    version="1.0.0"
)

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请替换为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（前端页面）
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# 注册所有路由
app.include_router(student_api.router)
app.include_router(class_api.router)
app.include_router(teacher_api.router)
app.include_router(exam_api.router_exam)
app.include_router(employment_api.router)
app.include_router(statistics_api.router)
app.include_router(query_agent.router)
app.include_router(auth_api.router)   # 认证路由
# app.include_router(user_api.router)   # 认证路由

@app.get("/")
def root():
    return {"message": "学生管理系统运行成功！访问 /docs 查看接口，前端请访问 /static/index.html"}

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8080)