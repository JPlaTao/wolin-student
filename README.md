# 沃林学生管理系统

基于 FastAPI + SQLAlchemy + Vue 3 构建的教育管理平台，提供学生信息管理、班级/教师管理、考试成绩追踪、就业跟踪、数据统计看板，以及 AI 智能问答、文生图、邮件发送等扩展功能。

## 技术栈

| 技术 | 说明 |
|------|------|
| **FastAPI** | Web 框架，自动生成 OpenAPI 文档 |
| **SQLAlchemy 2.0** | ORM，MySQL 后端 |
| **Pydantic 2.x** | 请求/响应模型验证 |
| **Vue 3 + Element Plus** | 前端 UI（原生 ES Modules，零构建） |
| **ECharts** | 数据可视化图表 |
| **JWT** | 用户认证（admin/teacher/student 三级角色） |
| **Uvicorn** | ASGI 服务器 |
| **Python 3.12** | 运行时 |

## 功能

- **数据管理** — 学生、班级、教师、考试成绩、就业信息的 CRUD，逻辑删除
- **用户认证** — JWT 登录/注册，三级角色（admin/teacher/student）权限控制
- **仪表板** — 数据总览卡片、就业趋势图、成绩分布图、仪表盘面板
- **高级统计** — 年龄分布、班级男女比例、平均分排名、不及格名单、薪资排名、就业去向统计
- **AI 智能问答** — 自然语言查询学生数据（支持 Kimi/DeepSeek/OpenAI），流式响应，多轮对话记忆
- **林黛玉 Agent** — 古风人设 AI 聊天（独立会话隔离）
- **文生图** — 通义万相 wan2.6-t2i 模型生成图片
- **邮件发送** — 用户自行配置 SMTP（QQ/163），发送自定义邮件
- **主题切换** — 亮色/暗色/跟随系统，侧边栏折叠

## 快速开始

### 环境

- Python 3.10+
- MySQL 5.7+
- 可选：DashScope API Key（文生图/知识库）、DeepSeek/OpenAI API Key（AI 问答）

### 安装

```bash
# 1. 克隆
git clone <repo-url>
cd wolin-student

# 2. 创建虚拟环境（项目使用 .venv，不要用全局 Anaconda）
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash
# 或 .venv\Scripts\activate       # Windows CMD

# 3. 安装依赖
python -m pip install -r requirements.txt

# 4. 配置数据库
mysql -u root -p -e "CREATE DATABASE wolin_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# 然后用初始化 SQL 脚本建表（见 docs/ 或 schema 目录）

# 5. 配置
cp config.example.json config.json   # 编辑数据库连接、API 密钥等
cp .env.example .env                 # 编辑环境变量（密钥）

# 6. 启动
python main.py
# 或 .venv/Scripts/uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

访问 <http://localhost:8080/static/index.html> 进入前端界面，或 <http://localhost:8080/docs> 查看 Swagger API 文档。

### 配置说明

项目使用双层配置：

- **`config.json`** — 数据库连接、JWT 密钥、LLM 提供商、API 密钥、应用设置
- **`.env`** — 敏感信息（数据库 URL、JWT 密钥、API 密钥），优先级高于 config.json

> ⚠️ `config.json` 和 `.env` 包含敏感信息，不要提交到 Git 仓库。

## 架构

```
API 层 (api/)          → 路由处理器，参数校验，权限校验
  ↓
Service 层 (services/) → 业务协调（跨 DAO 操作、知识库、LLM、邮件）
  ↓
DAO 层 (dao/)          → 纯数据库操作，返回 dict
  ↓
Model 层 (model/)      → SQLAlchemy ORM 声明
```

- **日志系统**: 彩色终端输出、独立 `audit.log`（敏感操作审计）、`error.log`（错误日志）
- **错误处理**: 全局异常处理器，标准化 JSON 错误响应（含错误码/请求 ID/时间戳）
- **逻辑删除**: 所有实体表支持 `is_deleted` 软删除

## 项目结构

```
├── api/                  # FastAPI 路由
│   ├── auth_api.py       #   用户认证/注册/管理
│   ├── student_api.py    #   学生 CRUD
│   ├── class_api.py      #   班级 CRUD
│   ├── teacher_api.py    #   教师 CRUD
│   ├── exam_api.py       #   考试成绩 CRUD
│   ├── employment_api.py #   就业信息 CRUD
│   ├── statistics_api.py #   统计/图表数据
│   ├── query_agent.py    #   AI 智能问答（流式 SSE）
│   ├── lin_daiyu_agent.py#   林黛玉 AI 聊天
│   ├── image_gen.py      #   文生图
│   └── email_api.py      #   邮件发送
├── core/                 # 基础设施
│   ├── auth.py           #   JWT 创建/验证
│   ├── permissions.py    #   角色权限校验
│   ├── database.py       #   SQLAlchemy 引擎
│   ├── settings.py       #   配置加载（config.json + .env）
│   ├── exceptions.py     #   自定义异常类
│   └── exception_handlers.py
├── dao/                  # 数据访问层
├── model/                # ORM 模型
├── schemas/              # Pydantic 请求/响应模型
├── services/             # 业务逻辑层
│   ├── query_agent_service.py  # LLM 问答服务
│   ├── lin_daiyu_service.py    # 人设聊天服务
│   ├── knowledge_base.py       # Chroma 向量知识库
│   ├── email_service.py        # SMTP 邮件服务
│   └── student_service.py      # 学生+就业联动创建
├── middleware/            # ASGI 中间件
│   └── logging_middleware.py   # 请求日志 + 错误日志
├── utils/                # 工具
│   ├── logger.py         #   彩色日志 + 审计日志
│   ├── log_decorators.py #   API 日志装饰器
│   └── pagination.py     #   统一分页
├── static/               # 前端
│   ├── index.html        #   主页面（Vue 3 SPA）
│   ├── js/app.js         #   模块编排入口
│   ├── js/modules/       #   功能模块（auth/dashboard/chat/daiyu/...）
│   └── css/              #   主题 + 自定义样式
├── config.json           # 应用配置（不入库）
├── config.example.json   # 配置模板
├── .env                  # 环境变量（不入库）
└── main.py               # 应用入口
```

## API 文档

启动后访问：

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

认证方式：在 Swagger UI 中点击右上角 **Authorize**，输入 JWT Token（通过登录接口获取）。
