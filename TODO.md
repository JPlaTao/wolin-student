# TODO

## P1 — 开发环境整理 ✅

_结论：项目用 `.venv`（Python 3.12.10），Anaconda 全局（Python 3.13.5）不要动。_

- [x] 搞清楚 `.venv` vs Anaconda 全局环境的关系
  - 项目用 `.venv`，143 个包，全部依赖正确版本
  - Anaconda 全局 473 个包（含旧版 fastapi/SQLAlchemy 等），不要用
  - **140+ 个包重叠**，激活失败会静默回退到 Anaconda，是隐患
- [x] 修复 `activate` 脚本的硬编码旧路径
  - 原来指向 `D:\4.WorkSpace\wolin-student\.venv` → 当前是 `E:\01-Projects\wolin-student\.venv`
  - 已修复 4 个文件: `activate` / `activate.bat` / `activate.fish` / `activate.nu`
- [x] 明确后续开发的标准操作流程
  - `source .venv/Scripts/activate` 激活后用 `python -m pip`
  - 或直接 `.venv/Scripts/python -m pip`
  - ❌ 不要用 `pip install`（指向 Anaconda 全局）
  - ❌ 不要用 `source .venv/Scripts/activate` 之后再单独用 `pip`（Windows .exe 在 Git Bash 有问题）

## P1 — docs/ 目录整理 ✅

_已建立子目录结构并将现有文件归类。_

- [x] 建立子目录结构:
  - `docs/specs/` — 开发规格文档
  - `docs/arch/` — 架构/设计文档
  - `docs/handoffs/` — 项目交接文档
- [x] 将现有文件归类移入对应子目录
- [x] 创建 `docs/README.md` 说明各子目录用途
- [ ] CLAUDE.md 中无需要更新的 docs/ 路径引用（`knowledge_base.py` 中的 `docs/` 是代码路径，保持不变）

## 根目录清理 ✅

_清除了临时文件、旧文档、缓存、chroma_db。_

- [x] 删除: `commit_msg.txt`, `test.py`, `test_email.py`, `test_report.json`
- [x] 删除: `add_*_column.sql`, `database_init_test.sql`
- [x] 删除: `__pycache__/`, `.pytest_cache/`
- [x] 删除: `QUICKSTART.md`, `SETUP.md`, `README.en.md`
- [x] 删除: 根目录 `__init__.py`
- [x] 清空: `logs/`, `chroma_db/`

## P2 — 日志系统重构 ✅

_评估并重构项目日志，使其更可读、统一、实用。已完成。_

- [x] 评估现有日志的问题:
  - 终端输出无颜色，难以区分等级（INFO/WARN/ERROR）
  - 多模块日志格式不一致（`query_agent`、`middleware`、`api_logger` 等各有各的格式）
  - 敏感信息审计日志混杂在普通日志中
- [x] 设计新的日志格式规范（建议: 时间 | 级别 | 模块 | 消息）
- [x] 引入 `colorlog` 做彩色终端输出（自定义 `ConsoleFormatter`，逐字段 ANSI 染色）
- [x] 统一所有 logger 初始化方式，消除重复配置
- [x] 分离审计日志文件 — 新增独立 `audit.log` + `SensitiveOperationFilter`

## 后续

- [ ] 前端模型切换功能：如何在前端/后端层面支持用户切换 LLM 模型（Kimi ↔ DeepSeek ↔ OpenAI），不依赖改配置文件

## 待定任务（讨论/规划中）

### 用户权限系统（P1）
✅ 已完成（commit 8fd877f）

- [x] Step 1: 权限核心 — JWT 加 role + `require_role()` + `core/permissions.py`
- [x] Step 2: 注册管控 — 限制注册角色 + 用户列表加权限
- [x] Step 3: 业务 API 逐个加固 — student/class/teacher/exam/employment/email API
- [x] Step 4: 数据隔离 — DAO 层按角色过滤查询（依赖 Step 6 外键关联）
- [x] Step 5: 前端权限适配 — Tab 级 + 注册表单级权限控制
- [ ] Step 6: 用户-教师关联（为数据隔离铺路）

### 四大名著 RAG（P2）
_将 Chroma 替换为 Milvus，搭建四大名著知识检索 RAG_

- [ ] Milvus 环境搭建（容器部署）
- [ ] 数据准备：四大名著文本向量化
- [ ] 替换现有 chroma_db 逻辑，集成 Milvus
- [ ] RAG 查询 API + 前端展示

### 二阶段可选功能（P3）
_待权限系统就绪后依次实现_

- [ ] 期末评语生成器
- [ ] 违纪话术教练
- [ ] 公告润色助手
- [ ] 成绩诊断书
- [ ] 班会活动策划师
- [ ] 模拟面试官
- [ ] 智能分班/分组助手
- [ ] 校规 RAG

## 待办

- [x] **P0 — 登录回车提交**：登录界面支持回车键确认登录 ✅
- [ ] **P1 — 数据管理 Bug**：成绩管理 + 用户管理 Tab 获取不到数据，需排查修复
- [ ] **P1 — 重写 README.md**：项目文档更新
- [ ] **P2 — 前端设计原则文档**：梳理 UI 风格、交互规范，避免样式过度设计
- [ ] **P2 — 增强登录注册界面**：UI/UX 改进
- [ ] **P2 — 点选关键词生成头像**：注册流程中，点选关键词调用文生图 API 生成头像