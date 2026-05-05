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

## P2 — 日志系统重构

_评估并重构项目日志，使其更可读、统一、实用。_

- [ ] 评估现有日志的问题:
  - 终端输出无颜色，难以区分等级（INFO/WARN/ERROR）
  - 多模块日志格式不一致（`query_agent`、`middleware`、`api_logger` 等各有各的格式）
  - 敏感信息审计日志混杂在普通日志中
- [ ] 设计新的日志格式规范（建议: 时间 | 级别 | 模块 | 消息）
- [ ] 引入 `rich` 或 `colorlog` 做彩色终端输出
- [ ] 统一所有 logger 初始化方式，消除重复配置
- [ ] 必要时分离审计日志文件

## 后续

- [ ] 前端模型切换功能：如何在前端/后端层面支持用户切换 LLM 模型（Kimi ↔ DeepSeek ↔ OpenAI），不依赖改配置文件
