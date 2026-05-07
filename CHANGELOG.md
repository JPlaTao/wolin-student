# 变更日志

## 待办

### P0 — 让系统能用
- [ ] 成绩表格加班级/学号列（exam DAO JOIN class 表）
- [ ] 成绩表加分页（limit/offset 参数）

### P1 — 对话式 BI（替代现有 query_agent）
- [ ] 对话式 BI：自然语言 → 统计图表
  - 前端引入 ECharts（CDN 加载）
  - LLM Agent 两个 Tool：`call_statistics_api`（预置统计）+ `generate_sql_and_query`（动态 SQL）
  - 返回结构化数据 + 图表类型建议 → ECharts 渲染
  - 多轮会话记录
  - 废弃 `query_agent` 及其前端 Tab

### P2 — 教师实用工具
- [ ] 公告/通知润色助手
- [ ] 成绩波动诊断书
- [ ] 期末评语生成器

### P3 — 趣味聊天扩展
- [ ] 多角色聊天（扩展黛玉架构：面试官、英语陪练等）

---

## 历史

### 2026-05-06
**学生自助查成绩 + 用户-学号绑定**

改动文件：`model/user.py` `api/auth_api.py` `api/exam_api.py` `static/index.html` `static/js/app.js` `static/js/modules/auth.js` `static/js/modules/management.js` `migrations/V002__add_stu_id_to_users.sql`

- **用户-学生映射** — User 模型新增 `stu_id` 字段 (FK → stu_basic_info, unique, nullable)，注册/管理员编辑均可绑定学号，支持解绑
- **学生查分端点** — `GET /exam/my-scores`（student 角色专用），返回当前学生所有成绩
- **前端条件渲染** — 数据管理 Tab 对 student 角色开放，仅显示成绩管理子 Tab（只读，无编辑/删除）
- **用户管理修复** — `loadUsers` 未导出导致页面数据为空，`UserResponse` Pydantic v2 `model_config` 兼容性修复

### 2026-05-05
**日志系统重构**

改动文件：`utils/logger.py` `utils/log_decorators.py` `middleware/logging_middleware.py` `main.py` 及 5 个 service/api 模块

- **终端彩色化** — 自定义 `ConsoleFormatter`，逐字段 ANSI 染色（级别名按严重程度分色、HTTP 方法按语义分色、状态码按范围分色），文件日志保持纯文本
- **消息格式标准化** — 全模块统一 `[request_id] [ModuleTag] Message` 格式，覆盖 Middleware、QueryAgent、KnowledgeBase、Email、ExceptionHandler 等 8 个模块
- **审计日志分流** — 新增独立 `audit.log` + `SensitiveOperationFilter`，敏感操作仅写入 audit.log
- **日志去重** — `@log_api_call` 每条请求由 4 行降至 2 行 middleware 日志
- **uvicorn access log 关闭** — 三级抑制，解决 0.43.0 reload 子进程重置日志级别问题

**文档** — `docs/specs/log-refactor-spec.md` `docs/handoffs/log-refactor-handoff.md`

**仓库整理** — 根目录清理、docs 按 specs/arch/handoffs 分层、`.gitignore` 添加 `.claude/`

**远端配置** — 双推：Gitee (HTTPS) + GitHub (SSH)

**林黛玉 Agent** — SSE 流式对话，独立会话隔离，前端"黛玉智能"Tab

**前端 ES Module 重构** — 1455 行 app.js → 163 行纯编排层 + 8 个功能模块
