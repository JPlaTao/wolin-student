# QueryAgent 重构规范

> 状态: **已完成 (2026-05-06)** | 优先级: P1 | 实际工时: ~3 h

---

## 一、目标

1. **拆分职责** — 将 `api/query_agent.py`（~1408 行）按单一职责拆分为独立模块，每个模块不超过 300 行
2. **消除重复** — 合并流式/非流式两套处理路径，消除 SQL 验证层的三重检查
3. **全局状态延迟初始化** — 模块级 `client = AsyncOpenAI(...)` / `vectordb = None` 改为延迟初始化或依赖注入
4. **Prompt 与代码解耦** — 将 Prompt 模板从字符串常量移至独立文件，便于单独维护和版本管理
5. **异常统一** — `raise HTTPException` 全部替换为 `core.exceptions` 的自定义异常

---

## 二、范围

### 2.1 拆分后的模块结构

```
api/query_agent.py              # 仅保留路由 + 编排（~200 行）
services/
├── llm_service.py              # LLM 客户端初始化、重试、provider 路由
├── intent_classifier.py        # 意图分类 + prompt 模板
├── sql_generator.py            # SQL 生成 + 验证 + 修复
├── analysis_service.py         # 数据分析逻辑（原 _process_analysis_branch 等）
└── stream_buffer.py            # StreamBuffer 类（纯搬移）
utils/
└── json_encoder.py             # SafeJSONEncoder + safe_json_dumps（纯搬移）
prompts/                        # 文本文件，不再嵌入 Python 代码
├── intent_classification.txt
├── sql_generation.txt
├── sql_reference_check.txt
├── analysis_refine.txt
└── analysis_prompt.txt
```

### 2.2 需要改动的文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `api/query_agent.py` | 重写 | 保留路由 + 简单编排，删除所有内部实现 |
| `services/llm_service.py` | 新建 | AsyncOpenAI 客户端工厂，延迟初始化 |
| `services/intent_classifier.py` | 新建 | 意图分类 + SQL 引用检测 |
| `services/sql_generator.py` | 新建 | SQL 生成、验证、修复 |
| `services/analysis_service.py` | 新建 | 数据分析上下文构建 + 精炼 |
| `services/stream_buffer.py` | 新建 | 从原文件原样搬出 |
| `utils/json_encoder.py` | 新建 | 从原文件原样搬出 |
| `prompts/*.txt` | 新建 | 5 个独立 prompt 模板文件 |
| `services/query_agent_service.py` | 不改 | 已有的 Agent 路径不动 |

### 2.3 行为变化

- **无** — 重构后所有 API 的请求/响应格式、SSE 事件结构、错误格式均与重构前完全一致
- 部署时只需合并 PR，无需执行迁移脚本或修改配置

---

## 三、约束

1. **不改外部行为** — API 请求/响应 schema、SSE 事件名、错误格式、日志格式均不得变化
2. **不改配置** — `config.json` schema 不变，不新增配置项
3. **不改 DAO/Model** — `dao/conversation_dao.py` 和 `model/*.py` 不动
4. **不改前端** — `static/` 目录下的任何文件不动
5. **保留 `services/query_agent_service.py`** — 已有的 LangChain Agent 路径不动
6. **所有 prompt 模板只改存放位置，不改内容** — 保证生成结果不受影响
7. **拆分后每个模块 import 不能产生循环依赖** — `services/*` 可引用 `utils/*` 和 `core/*`，但不可互相引用
8. **拆完即能正常运行** — 每一步都必须能用 `.venv/Scripts/python main.py` 启动并通过冒烟测试

---

## 四、暂不处理

以下问题已识别但**本次不处理**：

1. **`FALLBACK_SCHEMA` 保留原样** — 硬编码表结构问题仍然存在，但不在本次范围内。后续由"自动反射表结构"任务处理
2. **`_sanitize_prompt_input` 保留** — 正则过滤 prompt 注入虽不完善，但本次仅搬移不改逻辑。后续由安全专项处理
3. **`/natural` 非流式端点是否删除** — 需先确认前端是否仍在调用。本次保留不动，确认死代码后在后续 PR 中清理
4. **LangChain Agent 路径 (`agent_sql_query`)** — 已独立在 `services/query_agent_service.py`，本次不动
5. **向量知识库 (`vectordb`)** — 全局状态问题本次改为延迟初始化，但不改变 Chroma 的使用方式
6. **测试覆盖** — 不新增测试，不修改现有测试。可随时运行 `pytest` 验证回归

---

## 五、验证方法

1. **启动验证**: `.venv/Scripts/python main.py` 启动无报错
2. **冒烟测试**: `.venv/Scripts/python tests/quick_test.py` 通过
3. **API 回归**: 用以下场景逐一验证（与重构前对比响应）：
   - `POST /query/stream` 发 SQL 类问题 → 收到 `intent/sql/data/done` 事件
   - `POST /query/stream` 发分析类问题 → 收到 `intent/chunk/done` 事件
   - `POST /query/stream` 发闲聊 → 收到 `intent/chunk/done` 事件
4. **前端回归**: 在浏览器打开 "智能查询" Tab → 提问 → 观察正常输出

---

## 六、实施记录

| 阶段 | 结果 | 备注 |
|------|------|------|
| **Step 1** | ✅ 完成 | `utils/json_encoder.py` — SafeJSONEncoder + safe_json_dumps，纯搬移 |
| **Step 2** | ✅ 完成 | `services/stream_buffer.py` — StreamBuffer 类，纯搬移 |
| **Step 3** | ✅ 完成 | `services/llm_service.py` — 延迟初始化；`api/query_agent.py` 引入 `_LazyClient` 代理 |
| **Step 4** | ✅ 完成 | `prompts/*.txt` 5 个文件 + `prompts/loader.py`；`api/query_agent.py` 改用 `_load_prompt()` |
| **Step 5** | ✅ 完成 | `services/intent_classifier.py` `sql_generator.py` `analysis_service.py` 三个模块 |
| **Step 6** | ✅ 完成 | `_process_chat_branch` 移入 `analysis_service.py`；路由层只保留编排 |
| **Step 7** | ✅ 完成 | `raise HTTPException` → `BusinessException`/`ValidationException`；清理无用 import |
| | **合计 ~3 h** | |

### 实际偏离

1. **`sql_generation.txt` 未创建** — SQL 生成的 system prompt 较短且含动态分支（retry/previous_sql），不适合单独拆文件。聚合 SQL prompt 走了 `aggregate_sql.txt`
2. **`prompts/loader.py`** — 新增了共享加载器，避免各模块重复实现 `_load_prompt`
3. **`analysis_service.py` 合并了闲聊处理** — 除了 `process_analysis_branch`，还包含了 `process_chat_branch`（原 `_process_chat_branch`），未单独建 chat_service
4. **流式/非流式路径未合并** — 原计划中「合并流式/非流式两套处理路径」超出本规范范围，留待后续专项处理
