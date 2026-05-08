# 变更日志

## 待办

### P0 — 让系统能用
- [x] BI 对话历史与会话管理 — 2026-05-08
- [x] 成绩表格加班级/学号列（exam DAO JOIN class 表）— 2026-05-08
- [x] 成绩表加分页（limit/offset 参数）— 2026-05-06

### P1 — 对话式 BI（替代现有 query_agent）
- [x] 对话式 BI：自然语言 → 统计图表 — 2026-05-07
  - 前端引入 ECharts（CDN 加载）
  - LangGraph Agent 三个 Tool：`generate_sql` + `execute_sql` + `analyze_data`
  - 返回结构化数据 + 图表类型建议 → ECharts 渲染
  - 多轮会话记录（bi_ 前缀 session 隔离）
  - 前端"数据对话"Tab 替代旧"智能查询"Tab（文本优先 + 数据折叠布局）

### P2 — 教师实用工具
- [ ] 公告/通知润色助手（spec 已定稿，待实现）
- [ ] 成绩波动诊断书（spec 已定稿，待实现）
- [ ] 期末评语生成器（spec 已定稿，待实现）

### P3 — 趣味聊天扩展
- [ ] 多角色聊天（扩展黛玉架构：面试官、英语陪练等）

---

## 历史

### 2026-05-08
**BI 对话历史与会话管理 + 多个 Bug 修复 + 记忆系统 + 收尾技能**

- **记忆系统** — 新建 5 条记忆（UI 布局偏好 / schema 位置 / 错误提示规范 / 响应式渲染 / AI Chat V2 状态），更新 LangChain 学习目标，创建 MEMORY.md 索引（19 条记忆），诊断记忆未维护根因
- **轮次收尾技能** — `.claude/skills/wrap.md`，7 步管线：审计改动 → 检查 Spec 状态 → 更新 CHANGELOG → 检查记忆 → 提交 → 推送 → 收尾报告
- **Spec 文件整理** — `user-permission-plan` 重命名提交，`todo_bi-chat-ui-redesign` → `working_`，`working_ai-chat-v2-architecture` → `complete_`
- **P0 成绩表修复** — `exam_get()` 三表 LEFT JOIN 返回 `stu_name` + `class_name`，学生自查成绩表加班级和姓名列
- **BI 对话历史与会话管理** — 刷新页面后聊天不再空白
  - 后端新增 `GET /bi/sessions` + `GET /bi/sessions/{session_id}` 端点和对应 DAO
  - 前端会话 tab 栏（切换/新建/历史加载），刷新后自动恢复上次会话
  - 会话隔离：每个会话独立对话历史，互不干扰
- **BI Bug 修复**
  - SSE 解析器：TCP 分块边界处理，事件不丢失
  - SQL 子查询：去除尾部分号解决 `COUNT(*)` 包装失败
  - 表名修正：LLM 输出 `student` → `stu_basic_info`
  - SQL 错误前端可见：`success: false` 状态显示友好提示
  - Markdown 表格 CSS：Tailwind 重置后恢复边框和斑马纹

### 2026-05-07
**对话式 BI V2 — LangGraph Agent 替代 QueryAgent**

改动文件：`services/bi_agent.py` `api/bi_agent.py` `schemas/bi_analysis.py` `static/js/modules/biChat.js` `main.py` `static/js/app.js` `static/index.html`

- **LangGraph Agent** — `create_agent` + 3 个独立 Tool（generate_sql / execute_sql / analyze_data），替代 V1 手写意图分类
- **SSE 流式** — `agent.astream_events(version="v2")`，事件映射：thinking/sql/data/analysis/chunk/done
- **结构化分析输出** — `AnalysisOutput` Pydantic schema（summary + key_findings + chart_suggestion + statistics），含 JSON fallback
- **SQL 缓存 + 分页** — 内存 30min TTL 缓存，首页 50 条 + `POST /bi/data-page` 翻页
- **前端重构** — 消息从单 `v-html` 改为独立响应式字段 + Vue 模板逐块渲染；文本优先 + 数据折叠布局；ECharts 图表；用户友好错误提示

**文档** — `docs/specs/working_ai-chat-v2-architecture.md` `docs/specs/todo_bi-chat-ui-redesign.md`（实现记录见 spec）

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
