# 日志系统重构 — 轮次交接

## 本轮目标

日志系统重构：终端彩色化、消息格式规范化、审计日志分流、日志去重、关闭 uvicorn access log。

## 完成项

### 1. 终端输出彩色化 — `utils/logger.py`

- 新增 `ConsoleFormatter`（`logging.Formatter` 子类），逐字段手动 ANSI 染色，不依赖 `colorlog`
- 级别名染色：`DEBUG`=青 → `INFO`=绿 → `WARNING`=黄 → `ERROR`=红 → `CRITICAL`=红底
- HTTP 方法染色：`GET`=青、`POST`=绿、`PUT`/`PATCH`=黄、`DELETE`=红
- HTTP 状态码按范围染色：2xx=绿、3xx=黄、4xx/5xx=红
- 其余字段终端默认色，文件 Handler 保持纯文本

### 2. 消息格式标准化

规范化格式：`[request_id] [ModuleTag] Message body`

涉及的模块改动：

| 文件 | 改动 |
|------|------|
| `middleware/logging_middleware.py` | 添加 `[Middleware]` 标签；URL 格式从完整 URL 改为 `path?query` |
| `services/query_agent_service.py` | 约 40 条日志统一 `[QueryAgent]` 标签、`[{session_id[:8]}]` 格式 |
| `services/knowledge_base.py` | 约 12 条日志添加 `[KnowledgeBase]` 前缀 |
| `services/email_service.py` | `[邮件发送]` → `[Email]` |
| `core/exception_handlers.py` | 添加 `[ExceptionHandler]` 标签 |
| `api/email_api.py` | `[邮箱配置]` → `[EmailAPI]` |
| `utils/log_decorators.py` | `@log_api_call` 仅保留 ERROR 日志（去掉"开始"/"成功" INFO）；`[敏感操作]` → `[SensitiveOp]`；`[API]` 标签 |
| `main.py` | 添加 `[Main]` 标签；模块级 + startup 事件双重抑制 uvicorn.access |

### 3. 审计日志分流 — `utils/logger.py`

- `setup_logger()` 新增 `audit.log`（RotatingFileHandler, 10MB × 5, WARNING 级别）
- 新增 `SensitiveOperationFilter`，根据 `record.operation_type == 'sensitive'` 过滤
- 敏感操作仅写入 `audit.log`，被 `app.log` 的 `file_handler` 排除

### 4. 日志去重

- `@log_api_call` 去掉成功/开始的 INFO 日志，仅保留异常时的 ERROR 日志
- 每条请求输出 2 行 middleware 日志：请求到达 + 响应完成（含耗时和状态码）

### 5. uvicorn access log 关闭

- **问题**：uvicorn 0.43.0 的 `_subprocess.py:76` 在 `--reload` 子进程中调用 `config.configure_logging()`，使用 `logging.config.dictConfig()` 重置 `uvicorn.access` 日志级别为 INFO
- **解决**：`main.py` 三层防御：
  1. 模块级 `logging.getLogger("uvicorn.access").setLevel(logging.WARNING)`
  2. `utils/logger.py` 的 `setup_logger()` 中 `handlers.clear()`
  3. `@app.on_event("startup")` 中再次 `setLevel(WARNING)`（运行最晚，不受子进程影响）

## 验证结果

- 终端染色：确认生效，颜色语义正确
- uvicorn access log：确认关闭，启动后无 `INFO: 127.0.0.1:xxx - "GET ..."` 行
- 审计日志隔离：确认 `@log_sensitive_operation` 日志写入 `audit.log`，排除于 `app.log`
- 日志去重：确认每条请求仅 2 行 middleware 日志
- 零 Warning 启动，已有功能无回归

## 关键文件清单

| 文件 | 性质 | 备注 |
|------|------|------|
| `utils/logger.py` | 核心 | ConsoleFormatter 染色逻辑、SensitiveOperationFilter、audit.log |
| `utils/log_decorators.py` | 关键 | @log_api_call 去重、@log_sensitive_operation 审计标记 |
| `middleware/logging_middleware.py` | 关键 | 请求生命周期日志 |
| `main.py` | 关键 | startup 事件抑制 uvicorn.access、模块注册 |
| `services/query_agent_service.py` | 修改 | 最大量日志格式化 |
| `services/knowledge_base.py` | 修改 | [KnowledgeBase] 前缀 |
| `services/email_service.py` | 修改 | [Email] 前缀 |
| `core/exception_handlers.py` | 修改 | [ExceptionHandler] 前缀 |
| `api/email_api.py` | 修改 | [EmailAPI] 前缀 |
| `docs/specs/log-refactor-spec.md` | 文档 | 规约 + 实做差异记录 |

## 遗留 / 暂不处理

- JSON 结构化日志（当前无机器消费需求）
- 日志集中收集（ELK / Loki / Grafana 等）
- LLM 调用日志单独拆分（query_agent 量不大，暂不需要）
- 数据库慢查询日志（SQLAlchemy 层面配置）
- TimedRotatingFileHandler（基于大小的轮转够用）
- 前端界面 markdown 渲染修复 — 记录在 `docs/handoffs/todo.md`
- 日志功能扩展（加表 + 日志统计）— 记录在 `docs/handoffs/todo.md`
