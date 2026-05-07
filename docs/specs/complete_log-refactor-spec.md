# 日志系统重构 — 实施规约

> 状态: 已完成 (2026-05-05) | 优先级: P1 | 预估工时: ~3 h

## 目标

在不改变现有日志行为的前提下，解决终端可读性差、消息格式混乱、审计日志混杂三个问题，实现一次统一配置、全模块生效的日志体验升级。

## 范围（4 条主线）

### 1. 终端输出彩色化 — `utils/logger.py` 单文件改动

- 控制台 Handler 改用 `colorlog` 的 `ColoredFormatter`
- 级别颜色映射：`DEBUG` 灰 → `INFO` 青 → `WARNING` 黄 → `ERROR` 红 → `CRITICAL` 红底
- 文件 Handler 保持纯文本不变
- 全局 Logger 行为不变（已有 logger 实例自动继承颜色格式）
- `setup_logger()` 签名不变

### 2. 消息格式规范化 — 逐个模块统一消息风格

当前各模块消息风格不统一，规范后每行日志的格式：

```
[request_id] [ModuleTag] Message body
```

规范要求：

| 字段 | 规则 | 示例 |
|---|---|---|
| request_id | 有则写，无则省略（不写 `unknown`） | `[a1b2c3d4]` |
| ModuleTag | 中括号 + 模块简称，与 logger name 一致 | `[Middleware]` `[Email]` `[QueryAgent]` |
| Message body | 首句概括动作，后续补充细节 | `创建学生成功 (stu_id=42)` |

涉及的模块逐个调整：`query_agent.py` / `email_service.py` / `knowledge_base.py` / `exception_handlers.py` / `middleware/*`。

`@log_api_call` `@log_service_call` `@log_dao_operation` 三个装饰器的消息格式一并纳入上述规范。

### 3. 审计日志分流 — 新增独立 audit.log

- `setup_logger` 新增 `audit.log`（RotatingFileHandler，10MB × 5）
- `@log_sensitive_operation` `@log_mass_operation` 产生的日志写入 `audit.log` 且**不写入** `app.log`
- 实现方式：为 audit handler 绑定独立的 `logging.Filter`，根据日志中的 `operation_type=sensitive` 标记过滤

### 4. 日志去重 — 中间件 vs 装饰器职责梳理

**原则**：中间件负责请求生命周期（何时来、何时走、耗时、状态码），装饰器负责业务语义（做了什么、结果如何）。

现有流程：

```
Middleware:  Request started: POST /api/student  ← 保留
Decorator:   创建学生开始: {...}                   ← 去掉（与 middleware 已覆盖的信息重叠）
Decorator:   创建学生成功                          ← 去掉
Middleware:  Request completed: 200, 0.3s         ← 保留
```

去掉 `@log_api_call` 中的「开始」和「成功」两条 INFO 日志，只保留异常时的 ERROR 日志。业务语义由中间件的 `process_time` + `status_code` 覆盖。

`@log_service_call` 和 `@log_dao_operation` 保持不变（它们用 DEBUG 级别，不影响终端输出，且对调试有用）。

## 约束

1. `get_logger(name)` 的接口签名不变，已有 9 个模块的调用处一行不改
2. `setup_logger()` 的签名不变
3. 文件日志的轮转策略不变（RotatingFileHandler, 10MB × 5）
4. 日志目录不变（`logs/`）
5. 不引入除 `colorlog` 以外的新的第三方依赖
6. 每条主线的改动必须保证启动时零 Warning、已有功能零回归

## 暂不处理

- JSON 结构化日志（当前无机器消费需求）
- TimedRotatingFileHandler（当前基于大小的轮转够用）
- 日志集中收集（ELK / Loki / Grafana 等，目前为时过早）
- 引入 `rich` 作为日志依赖（当前用自定义 ANSI 染色，无需额外依赖）
- LLM 调用日志单独拆分（query_agent 的 LLM 调用日志量不大，暂不需要独立文件）
- 数据库慢查询日志（SQLAlchemy 层面配置，不属于本项目日志系统）

---

## 实现记录（实做 vs 规约差异）

| # | 规约 | 实际实现 | 原因 |
|---|------|----------|------|
| 1 | 使用 `colorlog.ColoredFormatter` | 自定义 `ConsoleFormatter(logging.Formatter)`，逐字段手动 ANSI 染色 | `colorlog` 将整行染为同一颜色，无法做到 uvicorn 风格（仅级别名染色，其余字段默认色），且无法按 HTTP 方法语义区分颜色 |
| 2 | 级别颜色: DEBUG灰→INFO青→WARNING黄→ERROR红→CRITICAL红底 | INFO 改为绿色（同 uvicorn 习惯），其余一致 | 青色在终端可读性不如绿色，与会话历史的用户反馈对齐 |
| 3 | 依赖新增 `colorlog>=6.10.0` | 未引入 `colorlog`，`requirements.txt` 无变更 | 自定义 Formatter 即可满足需求，减少外部依赖 |
| 4 | request_id 规则："有则写，无则省略" | 实际统一写 `[request_id]`，无 request_id 时写 `unknown` | middleware 总是生成 request_id，装饰器 fallback 写 `unknown` 避免格式断裂；当前已与 exception_handlers 对齐 |
| 5 | 仅 4 条主线 | 新增第 5 条"关闭 uvicorn access log" | 调试过程中发现 uvicorn access log 与自定义 middleware 日志重复，需彻底关闭 |
| 6 | uvicorn.access 抑制：在 `setup_logger()` 中 `setLevel(WARNING)` | 三级抑制：①模块级 `setLevel(WARNING)` ②`setup_logger` 中 `handlers.clear()` ③`@app.on_event("startup")` 中再次 `setLevel(WARNING)` | uvicorn 0.43.0 的 `_subprocess.py:76` 在 reload 子进程中调用 `config.configure_logging()` 重置所有日志级别，前两级会被覆盖，startup 事件是最后防线 |

## 验证结果

- **终端染色**：INFO=绿、WARNING=黄、ERROR=红、CRITICAL=红底；HTTP 方法按语义染色（GET=青、POST=绿、PUT/PATCH=黄、DELETE=红）；状态码按范围染色（2xx=绿、3xx=黄、4xx/5xx=红）
- **uvicorn access log 关闭**：确认启动后无 `INFO: 127.0.0.1:xxx - "GET ..."` 行。启动时的 `INFO: Started server process` 等为 uvicorn 进程日志，属正常行为
- **审计日志分流**：`@log_sensitive_operation` 产生的日志仅写入 `audit.log`，未写入 `app.log`
- **消息格式标准化**：`[request_id] [ModuleTag] Message` 格式覆盖 Middleware、QueryAgent、Email、KnowledgeBase、ExceptionHandler、EmailAPI、log_api_call 装饰器
- **日志去重**：每条请求 2 行 middleware 日志（开始 + 完成），不再有装饰器的重复 "开始"/"成功" INFO 行
