# 变更日志

## [2026-05-05]

### 日志系统重构

对日志系统进行了全面重构，覆盖 terminal 输出、消息格式、审计日志、日志去重和 uvicorn access log 抑制。

**改动文件：** `utils/logger.py` `utils/log_decorators.py` `middleware/logging_middleware.py` `main.py` 及 5 个 service/api 模块

- **终端彩色化** — 自定义 `ConsoleFormatter`，逐字段 ANSI 染色（级别名按严重程度分色、HTTP 方法按语义分色、状态码按范围分色），文件日志保持纯文本
- **消息格式标准化** — 全模块统一 `[request_id] [ModuleTag] Message` 格式，覆盖 Middleware、QueryAgent、KnowledgeBase、Email、ExceptionHandler 等 8 个模块
- **审计日志分流** — 新增独立 `audit.log` + `SensitiveOperationFilter`，敏感操作仅写入 audit.log，排除于 app.log
- **日志去重** — `@log_api_call` 去掉"开始"/"成功"INFO 行，仅保留 ERROR；每条请求由 4 行降至 2 行 middleware 日志
- **uvicorn access log 关闭** — 三级抑制（模块级 setLevel → setup_logger handlers.clear → startup 事件），解决 uvicorn 0.43.0 reload 子进程重置日志级别问题

### 文档

- **`docs/specs/log-refactor-spec.md`** — 日志重构实施规约 + 实做差异记录
- **`docs/handoffs/log-refactor-handoff.md`** — 轮次交接文档

### 仓库整理

- 根目录清理：删除遗留临时文件（旧文档、SQL 脚本、测试文件）
- 目录归类：docs 按 specs/arch/handoffs 分层
- `.gitignore` 添加 `.claude/`

### 远端配置

- 支持双推：`git push` 同时推送 Gitee (HTTPS) + GitHub (SSH)
