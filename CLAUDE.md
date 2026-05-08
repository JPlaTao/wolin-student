# CLAUDE.md

本文件用于指导 Claude Code (claude.ai/code) 在该仓库中工作。

## 约束

- 当提问本身有问题时，回答它是帮倒忙。先修正提问，再回答。 Debug the question first.

- 我给你挑战我的安全空间，用好这个权限。指出逻辑漏洞是尊重，不是冒犯。 Truth over comfort.

- 执行完动作给我汇报的时候, 说明清楚你是如何测试验证的, 是通过哪些证据支持你确认你确实完成了我给你的需求

### 多 Agent 并行开发规则

当多个 Agent 同时在同一个项目中工作，必须遵循以下规则防止冲突：

1. **API-first** — 任何需要前后端联动的功能，先产出 API spec（method + path + request/response schema），冻结后再开 worktree。

2. **Worktree 隔离** — 每个 Agent 必须通过 `EnterWorktree` 在独立 git worktree 中工作。严禁多个 Agent 共享同一个工作目录。

3. **越界禁止** — 后端 Agent 只动 `api/` `services/` `dao/` `schemas/` `model/` `main.py`。前端 Agent 只动 `static/`。越界即拒绝。

4. **Mock 驱动前端** — 前端基于 API spec 造 mock 数据实现渲染，不依赖后端端点可用性。

5. **串行共享文件** — `core/` `config.json` `migrations/` 只串行改，一人动完确认后再安排下一个人。

6. **先后端再前端合并** — 后端分支先合入 master，前端再合并（确保联调时真实 API 可用）。

7. **纯前端/纯后端改动** — 不涉及前后端联动的改动（如只改 `static/` 或只改 API），无需 AW 流程，直接 worktree 开干。

## 项目概览

沃林学生管理系统 (Wolin Student Management System) — 基于 FastAPI + SQLAlchemy + MySQL 构建的教育管理系统，提供 RESTful API 和原生 JavaScript 前端。系统管理学生、班级、教师、考试成绩、就业跟踪和统计信息，同时包含 AI 智能问答 Agent、文生图、知识库和邮件发送功能。

## 常用命令

> ⚠️ **Python 环境**: 项目使用 `.venv`（Python 3.12.10）。不要依赖系统全局的 Anaconda Python（3.13.5）。
> 所有命令都要通过 `.venv/Scripts/` 或 `source .venv/Scripts/activate` 激活后执行。

```bash
# 启动服务（推荐 — 直接指定路径，不依赖激活）
.venv/Scripts/python main.py
.venv/Scripts/uvicorn main:app --reload --host 0.0.0.0 --port 8080

# 或者先激活再运行（activate 脚本已修复路径）
source .venv/Scripts/activate
python main.py
uvicorn main:app --reload --host 0.0.0.0 --port 8080
deactivate   # 退出虚拟环境

# 安装/管理依赖（二选一）
.venv/Scripts/python -m pip install -r requirements.txt   # 直接指定（推荐）
source .venv/Scripts/activate && python -m pip install <包> && deactivate  # 激活后
# ❌ 不要用 pip install 或 pip3 — 它们指向 Anaconda 全局环境

# 运行测试
.venv/Scripts/python -m pytest tests/test_api.py -v

# 快速冒烟测试
.venv/Scripts/python tests/quick_test.py
```

## 架构

### 分层结构 (API → Service → DAO → Model)

- **`api/`** — FastAPI 路由处理器。每个模块定义一个 `APIRouter`，所有端点通过 `Depends(get_current_user)` 要求 JWT 认证。使用 `core.exceptions` 返回错误（重构良好的代码中不使用裸 `HTTPException`）。通过 `@log_api_call` / `@log_sensitive_operation` 装饰器记录日志。
  - `student_api.py`, `class_api.py`, `teacher_api.py`, `exam_api.py`, `employment_api.py`, `statistics_api.py` — CRUD 及查询端点
  - `auth_api.py` — 注册/登录、用户 CRUD（删除/更新仅管理员）
  - `bi_agent.py` — 对话式 BI Agent (LangGraph)，SSE 流式数据对话
  - `image_gen.py` — 文生图，通过通义万相 wan2.6-t2i (DashScope API)
  - `email_api.py` — 通过用户配置的 SMTP 发送邮件 (QQ/163)

- **`core/`** — 共享基础设施：
  - `database.py` — SQLAlchemy 引擎、`SessionLocal`、`get_db()` 依赖、`Base` 声明式基类
  - `settings.py` — 基于 Pydantic 的配置，从 `config.json` 加载（通过 `@lru_cache` 缓存）。包含 `DatabaseConfig`、`JWTConfig`、`APIKeysConfig`、`LLMConfig`、`AppConfig`
  - `auth.py` — JWT 创建/验证 (python-jose)、密码哈希 (pbkdf2_sha256)、`get_current_user` / `get_current_admin_user` 依赖
  - `exceptions.py` — 自定义异常体系：`AppException` → `BusinessException`、`ValidationException`、`NotFoundException`、`ConflictException`、`UnauthorizedException`、`ForbiddenException`、`TokenExpiredException` 等
  - `exception_handlers.py` — 在 `main.py` 中注册的全局异常处理器，生成包含错误码、请求 ID 和时间戳的标准化错误响应
  - `email_providers.py` — SMTP 服务商配置 (QQ, 163)

- **`dao/`** — 数据访问对象。纯数据库操作，不含业务逻辑。每个函数接收 `db: Session` 参数，返回字典/列表（而非序列化后的 ORM 对象）。学生和教师 DAO 通过 `utils.pagination` 支持分页。

- **`services/`** — 业务逻辑层（较薄，仅在需要跨 DAO 协调时使用）：
  - `student_service.py` — `create_student_with_employment()`（创建学生 + 空就业记录）、校验顾问角色和班级是否存在
  - `knowledge_base.py` — 使用 DashScopeEmbeddings + LangChain 从 docs/ 构建 Chroma 向量数据库
  - `email_service.py` — SMTP 邮件发送（支持 QQ/163，SSL）

- **`model/`** — SQLAlchemy ORM 模型。注意：
  - `student.py` — `StuBasicInfo` (stu_basic_info 表)，通过 `advisor_id` 关联教师，`class_id` 关联班级
  - `class_model.py` — `Class`，含 `class_teacher` 多对多关联表
  - `teachers.py` — `Teacher`，含角色字段 (counselor/headteacher/lecturer)
  - `employment.py` — `Employment`，关联学生和班级
  - `exam_model.py` — `StuExamRecord`，复合主键 (stu_id, seq_no)
  - `user.py` — `User`，含邮件配置字段（服务商、地址、授权码）
  - `conversation.py` — `ConversationMemory`，查询 Agent 的多轮对话记忆

- **`schemas/`** — Pydantic 请求验证和响应序列化模型。所有 API 响应使用 `ResponseBase(code, message, data)` 或 `ListResponse(data, total)`。

- **`utils/`** — `logger.py`（RotatingFileHandler + 控制台，独立 error.log）、`log_decorators.py`（API 调用日志、敏感操作审计、Service/DAO 日志）、`pagination.py`（统一分页工具）

- **`middleware/`** — `LoggingMiddleware`（带 UUID 的请求/响应计时）、`ErrorLoggingMiddleware`（未处理异常捕获）

- **`static/`** — 原生 JavaScript 前端（app.js、各功能模块、utils/api.js），模块化 CSS 支持主题切换。通过 `/static/index.html` 访问。

### 关键设计模式

1. **逻辑删除** — 所有实体表都有 `is_deleted` 布尔字段。查询始终过滤 `is_deleted == False`。部分 API 支持恢复端点。
2. **标准化错误处理** — `core/exceptions.py` 定义带错误码的类型化异常。`core/exception_handlers.py` 将其映射为包含 `code`、`message`、`detail`、`timestamp`、`request_id` 的 JSON 响应。
3. **配置管理** — `config.json`（JSON 文件，由 `core/settings.py` 通过 Pydantic 加载）。可通过 `CONFIG_PATH` 环境变量覆盖。`.env` 文件存放密钥。
4. **JWT 认证** — 基于 Token，使用 OAuth2PasswordBearer。Token 过期时间可配置。三个认证级别：`get_current_user`（任意登录用户）、`get_current_active_user`（仅活跃用户）、`get_current_admin_user`（仅管理员）。
5. **可配置的 LLM 提供商** — 通过 `config.json` 的 `llm.provider` 和 `llm.base_url` 支持 Kimi/Moonshot、DeepSeek、OpenAI。API 密钥在 `config.json` 的 `api_keys` 下。

### 数据库表

- `teacher` — 教师，含角色字段 (counselor/headteacher/lecturer)
- `class` — 班级，关联班主任；通过 `class_teacher` 与教师多对多关联
- `stu_basic_info` — 学生，关联班级和顾问辅导员
- `stu_exam_record` — 考试成绩，复合主键 (stu_id, seq_no)
- `employment` — 就业记录，关联学生和班级
- `users` — 系统用户（用于 JWT 认证），含邮件配置列
- `conversation_memory` — AI 查询 Agent 的对话历史
