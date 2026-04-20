import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from core.database import engine, Base
from core.settings import get_settings
from api import (
    student_api,
    class_api,
    teacher_api,
    exam_api,
    employment_api,
    statistics_api,
    query_agent,
    auth_api,
    image_gen,
    email_api
)
from services.knowledge_base import build_knowledge_base
from utils.logger import get_logger
from middleware.logging_middleware import LoggingMiddleware, ErrorLoggingMiddleware
from core.exception_handlers import register_exception_handlers

# 获取日志记录器和配置
logger = get_logger("main")
settings = get_settings()

# 创建所有表（包括 users）
Base.metadata.create_all(bind=engine)
logger.info("数据库表创建完成")

# 构建知识库（如果模型存在则构建，否则跳过，不影响其他功能）
try:
    build_knowledge_base()
    logger.info("知识库构建完成")
except Exception as e:
    logger.warning(f"知识库构建失败（不影响其他功能）: {e}")

app = FastAPI(
    title=settings.app.title,
    description="FastAPI + MySQL 学生信息/成绩/就业/统计管理",
    version=settings.app.version
)

# 注册全局异常处理器（必须在中间件之前注册）
register_exception_handlers(app)

# 添加日志中间件（需要在 CORS 之前添加）
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorLoggingMiddleware)

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(auth_api.router)  # 认证路由
app.include_router(image_gen.router)  # 文生图路由
app.include_router(email_api.router)  # 邮件路由


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>学生管理系统运行成功！</h1>
        <p><a href="/docs" target="_blank">Swagger 文档</a></p>
        <p><a href="/static/index.html" target="_blank">前端界面</a></p>
    </body>
    </html>
    """


if __name__ == '__main__':
    uvicorn.run(
        app,
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        access_log=False  # 关闭 Uvicorn 访问日志，使用自定义日志
    )
