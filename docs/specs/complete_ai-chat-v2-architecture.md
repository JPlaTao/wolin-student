# AI 智能问答 V2 — LangGraph Agent 架构设计

> 状态: 待实现 | 优先级: P1 | 预估工时: ~12-16 h

---

## 一、背景与动机

### 1.1 现状问题

当前 V1 实现（`api/query_agent.py` + `services/`）采用**意图分类 → 三分支路由**架构：

```
用户问题 → classify_intent_llm()
              │
              ├── "sql"      → generate_sql() → execute → 返回结果
              ├── "analysis"  → 读取上一轮 SQL 结果 → LLM 分析
              └── "chat"      → LLM 直接回复
```

三个核心问题：

1. **分支互斥，不能串联** — 一次请求只能走一条分支。"查数据 + 分析"需要用户手动发两轮消息，且第一轮不能直接要求分析。
2. **SQL 生成和执行耦合在一个大函数里** — `_stream_sql_processing()` 写了 80 行把生成、验证、执行、重试全串在一起，不可单独复用。
3. **分析依赖上一轮的隐式状态** — `build_analysis_context()` 通过 `get_latest_turn()` 从数据库拉上一轮的 SQL 结果，而不是从当前请求直接传入。这导致：用户的第一条消息不能是分析请求；如果中间有闲聊，链条断裂。

### 1.2 目标

用 **LangGraph StateGraph Agent** 完全重写，实现：

- **Tool 化**：SQL 生成 / SQL 执行 / 数据分析 各自是独立的 Tool，Agent 自行编排调用顺序
- **一次对话可串联多个 Tool**：用户说 "查一下五班成绩，分析为什么低" → Agent 自动调用 generate_sql → execute_sql → analyze_data，一次返回
- **结构化分析输出**：分析结果包含 `chart_suggestion`，为后续图表渲染（ECharts）提供数据基础
- **流式输出 + 多轮对话 + 会话隔离**：保留并增强现有 SSE 体验

---

## 二、整体架构

### 2.1 调用链路

```
┌─────────────────────────────────────────────────────┐
│ 前端                                                │
│   chat.js (重写)                                    │
│   POST /bi/stream (SSE)                             │
│   → 解析 SSE 事件 → 渲染 SQL/表格/图表/文本            │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ API 层: api/bi_agent.py (新建)                      │
│   POST /bi/stream                                   │
│   → 创建 LangGraph Agent                            │
│   → agent.astream_events()                          │
│   → 转换为 SSE 事件流                                │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ Agent 层: services/bi_agent.py (新建)               │
│   LangGraph StateGraph                              │
│   ┌──────────┐    ┌──────────────────────┐         │
│   │  agent   │───→│     tools 路由        │         │
│   │  (LLM)   │←───│  generate_sql         │         │
│   │          │    │  execute_sql          │         │
│   │          │    │  analyze_data         │         │
│   └──────────┘    └──────────────────────┘         │
│                                                      │
│   State: { messages, sql, query_result,             │
│             analysis, session_id, user_id }          │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 复用层 (不动或轻改)                                   │
│   services/sql_generator.py  — generate_sql()       │
│                              — execute_sql_to_dict() │
│                              — validate_sql()        │
│   dao/conversation_dao.py    — save_turn()           │
│                              — get_recent_turns()    │
│   model/conversation.py      — ConversationMemory    │
└─────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | **LangGraph StateGraph** | 比 `create_agent` 更可控，节点/边显式定义，便于流式调试 |
| 追踪 | **LangSmith** (可选) | 设置环境变量即可开启，用于调试 Agent 推理链路 |
| LLM 客户端 | **复用现有 AsyncOpenAI** | 与 `services/llm_service.py` 兼容，不改 config.json |
| 结构化输出 | **LangChain `with_structured_output()`** | 让 LLM 输出符合 Pydantic schema，而非手写 JSON 解析 |
| 会话存储 | **复用 `conversation_memory` 表** | 不改数据库 schema，加 `bi_` 前缀隔离 session |
| 流式方式 | **`agent.astream_events()`** | LangGraph 原生支持，可捕获每个 node/tool/llm_token 事件 |
| 大数据量处理 | **分页 + 统计摘要**，不截断 | Agent 收到第一页+统计；前端翻页时复用 SQL 重执行，不走 Agent |

---

## 三、LangGraph 状态图设计

### 3.1 State 定义

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class BIAgentState(TypedDict):
    # 对话历史（LangGraph 自动用 add_messages 合并）
    messages: Annotated[list[BaseMessage], add_messages]

    # 会话元信息
    session_id: str
    user_id: int

    # Tool 中间结果（Agent 在 Tool 调用间传递）
    generated_sql: str | None
    sql_hash: str | None           # SQL 的 MD5，前端翻页时回传
    query_result: dict | None      # QueryResult (见 4.2)
    analysis_result: dict | None   # AnalysisOutput (结构化)
```

### 3.2 节点与边

```
              ┌─────────────┐
              │   __start__  │
              └──────┬───────┘
                     │
                     ▼
              ┌─────────────┐
         ┌───→│   agent     │ (LLM 决策节点)
         │    │   (llm_call)│
         │    └──────┬──────┘
         │           │
         │     ┌─────┴─────┐
         │     │ 需要 Tool?  │
         │     └─────┬─────┘
         │       YES │     │ NO
         │           │     └──────────┐
         │           ▼                │
         │    ┌─────────────┐         │
         │    │  tools      │         │
         │    │  (tool_node)│         │
         │    └─────────────┘         │
         │           │                │
         └───────────┘                │
                                      ▼
                               ┌─────────────┐
                               │   __end__    │
                               └─────────────┘
```

单节点说明：

- **agent** — 组装 system prompt + 历史 messages → 调用 LLM。LLM 返回 `AIMessage`（可能包含 `tool_calls`）。
- **tools** — 执行 Tool 调用，将结果包装为 `ToolMessage` 追加到 state.messages。LangGraph 自动路由回 agent 节点。
- **条件边** — 检查最后一条 `AIMessage` 是否有 `tool_calls`：有 → 进入 tools 节点，无 → 结束。

### 3.3 Agent 循环示例

用户输入："查一下五班最近一次考试的成绩，分析为什么分数偏低"

```
Turn 1:
  agent → AIMessage(tool_calls=[generate_sql("五班最近一次考试成绩")])
  tools → generate_sql → "SELECT ... FROM stu_exam_record JOIN stu_basic_info ..."
          保存到 state.generated_sql

Turn 2:
  agent → AIMessage(tool_calls=[execute_sql(state.generated_sql)])
  tools → execute_sql → {
      columns: [...], rows: [50条...], row_count: 100,
      page: 1, total_pages: 2, has_more: true,
      statistics: {grade: {min:42, max:98, avg:71.3}, ...},
      sql_hash: "a1b2c3..."
  }
  保存到 state.query_result

Turn 3:
  agent → AIMessage(tool_calls=[analyze_data(state.query_result, "为什么分数偏低")])
  tools → analyze_data → AnalysisOutput(...)
          保存到 state.analysis_result

Turn 4:
  agent → AIMessage(content="根据分析，五班成绩偏低的主要原因有... [图表建议: bar]")
  (无 tool_calls → 结束)
```

---

## 四、三个 Tool 定义

### 4.1 Tool 1: `generate_sql`

```python
@tool
async def generate_sql(question: str, context: str = "") -> str:
    """根据自然语言问题生成 SQL 查询语句。context 可包含上一轮的 SQL 或过滤条件。"""
```

| 项目 | 说明 |
|------|------|
| 输入 | `question`: 用户想查什么；`context`: 可选的参考上下文 |
| 输出 | 纯 SQL 字符串 |
| 内部 | 调用 `services/sql_generator.generate_sql()`，内部自动检索 schema → LLM 生成 |
| schema 来源 | 优先从 vectordb 检索，否则用 `FALLBACK_SCHEMA` |

**设计要点**：Agent 可以自行决定传什么作为 `context`。比如用户说 "那个班的呢？"，Agent 从历史消息中提取上一轮 SQL 的关键过滤条件，拼入 `context` 参数。

### 4.2 Tool 2: `execute_sql`

```python
@tool
async def execute_sql(sql: str, page: int = 1, page_size: int = 50) -> dict:
    """执行只读 SQL 查询并返回分页结果 + 列统计。"""
```

| 项目 | 说明 |
|------|------|
| 输入 | `sql`: 完整的 SELECT 语句；`page`/`page_size`: 分页参数 |
| 输出 | `QueryResult`: `{columns, rows, row_count, page, page_size, total_pages, has_more, statistics, sql_hash}` |
| 内部 | `validate_sql()` 安全检查 → 计算 `total_count`（`SELECT COUNT(*)` 包装）→ `LIMIT/OFFSET` 执行 → 列统计计算 |

**分页设计**（替代 V1 截断）：

```
execute_sql 始终返回第一页数据（page_size=50），不做截断。
同时返回：
  - row_count: 总行数
  - total_pages: 总页数
  - has_more: 是否还有下一页
  - statistics: 每列的基本统计（数值列: min/max/avg，文本列: distinct 数量）
  - sql_hash: SQL 的 MD5，用于后续翻页
```

**为什么是"分页"而不是"截断"**：

| 对比 | 截断（V1） | 分页（V2） |
|------|-----------|-----------|
| 用户看到的数据 | 只有前 20 行，其余丢弃 | 第 1 页 50 行，可翻页浏览全部 |
| LLM 分析质量 | 基于截断数据，可能不准确 | 基于第一页 + 全量统计，Agent 可判断是否需要聚合 |
| 后续翻页 | 不支持 | 前端调 `/bi/data-page` 复用 SQL 重执行 |
| SQL 复用 | SQL 丢弃 | SQL 被 hash 缓存，翻页/导出均复用 |

**Agent 侧处理大数据量**：Agent 收到的 `query_result` 包含第一页 + 统计信息。如果 `has_more: true` 且用户要求分析，Agent 有两种选择：
1. 基于第一页 + 统计摘要直接分析（通常足够）
2. 调用 `generate_sql` 生成聚合查询 → 再调 `execute_sql` 拿聚合结果分析

#### 4.2.1 前端翻页端点

翻页不需要走 LangGraph Agent，直接调独立端点：

```python
# api/bi_agent.py
@router.post("/data-page")
async def get_data_page(req: PageRequest, db: Session = Depends(get_db)):
    """根据 sql_hash 获取指定页数据。不经过 Agent，直接执行 SQL。"""
    sql = get_cached_sql(req.sql_hash)  # 从 redis/memory/DB 获取
    if not sql:
        raise NotFoundException("SQL 已过期，请重新查询")
    result = await execute_sql_to_dict_with_page(db, sql, req.page, req.page_size)
    return ResponseBase(code=200, data=result)
```

前端翻页流程：
```
用户点"下一页"
  → POST /bi/data-page { sql_hash: "a1b2c3", page: 2 }
  → 后端从缓存取 SQL → LIMIT 50 OFFSET 50 → 返回第 2 页
  → 不重新生成 SQL，不走 Agent
```

### 4.4 Tool 3: `analyze_data`

```python
@tool
async def analyze_data(data_json: str, question: str) -> dict:
    """对查询结果进行数据分析，返回结构化分析结果。"""
```

| 项目 | 说明 |
|------|------|
| 输入 | `data_json`: `execute_sql` 返回的 JSON；`question`: 分析角度 |
| 输出 | `AnalysisOutput` (见第五章) |
| 内部 | LLM 调用 + `with_structured_output(AnalysisOutput)` |

**这是关键 Tool**：分析结果是结构化的 Pydantic 对象，不是自由文本。前端可以直接用 `analysis_result.chart_suggestion` 渲染图表。

### 4.5 Tool 粒度分析：生成/执行 合并 vs 分离

| 维度 | 合并（生成+执行一体） | 分离（生成/执行独立） |
|------|---------------------|---------------------|
| Agent 轮次 | 1 次 Tool 调用 | 2 次 Tool 调用 |
| 翻页复用 SQL | 需额外机制把 SQL 从 Tool 内部提取出来缓存 | SQL 天然独立存在，直接用 hash 引用 |
| 前端展示 SQL | 需要从 Tool 返回值中单独提取 | 独立 SSE 事件，前端直接展示 |
| Agent 审查 SQL | Agent 看不到中间产物 | Agent 可在生成后、执行前检查/修正 SQL |
| 错误恢复 | 执行失败 = 整个 Tool 失败，Agent 需重新生成 | Agent 看到错误后可修正 SQL 后再调 execute_sql |
| 灵活组合 | 无法跳过执行（如仅需生成 SQL 给用户确认） | 可只生成不执行，或生成后多次执行（翻页/导出） |

**结论：分离更优。** 2 次调用的开销是值得的——换来了翻页复用、前端透明、Agent 灵活编排、错误恢复四个关键能力。对于数据对话场景，"生成一次 SQL，执行多次（翻页/导出/聚合变体）"是核心需求，合并 Tool 反而会成为障碍。

### 4.6 SQL 缓存策略

`execute_sql` 执行后，SQL 需要被缓存以便前端翻页复用：

```
execute_sql(sql) 执行时:
  1. sql_hash = md5(sql)
  2. 缓存 SQL: cache.set(sql_hash, sql, ttl=1800)  # 30分钟过期
  3. 返回 QueryResult 中包含 sql_hash
  4. 前端翻页时: POST /bi/data-page { sql_hash, page: N }
  5. 后端从缓存取 SQL → 包装 LIMIT/OFFSET → 执行
```

缓存后端选择：**先用内存字典，后续可换 Redis**（30 分钟 TTL + LRU，不会占太多内存。每条 SQL ~200 bytes，1000 条才 200KB）。

---

## 五、结构化分析输出

### 5.1 Pydantic Schema

```python
from pydantic import BaseModel, Field

class ChartSuggestion(BaseModel):
    type: str = Field(description="图表类型: bar / line / pie / scatter / table")
    title: str = Field(description="图表标题，不超过15字")
    reason: str = Field(description="为什么推荐这个图表类型，给 Agent 内部分析用")

class AnalysisOutput(BaseModel):
    summary: str = Field(description="自然语言分析总结，2-4句话，面向最终用户")
    chart_suggestion: ChartSuggestion | None = Field(
        default=None,
        description="如果数据适合可视化，给出图表建议；纯文本数据则留空"
    )
    key_findings: list[str] = Field(description="关键发现列表，每条一句话")
    statistics: dict = Field(
        default_factory=dict,
        description="关键统计数据，如 {avg: 78.5, max: 98, min: 42, trend: '下降'}"
    )
```

### 5.2 前端消费方式

前端收到 SSE 事件 `analysis` 后：

```javascript
// analysis_result 直接对应 AnalysisOutput
if (analysis.chart_suggestion) {
    const { type, title } = analysis.chart_suggestion;
    const option = buildEChartsOption(type, title, analysis.statistics, queryResult);
    myChart.setOption(option);
}
// summary 和 key_findings 渲染为文本
```

### 5.3 为什么用结构化输出

| 对比 | 自由文本 | 结构化 |
|------|---------|--------|
| 前端渲染图表 | 需要二次解析，容易出错 | 直接取字段 |
| 后续 BI 扩展 | 需重新设计 | 扩展 Pydantic schema 即可 |
| Agent 内部分析 | 不透明 | `key_findings` 可供下一轮 Agent 引用 |
| 调试 | 难以验证格式 | Pydantic 自动校验 |

---

## 六、流式输出设计

### 6.1 SSE 事件类型

使用 LangGraph 的 `astream_events()` 捕获执行过程，映射为 SSE 事件：

| SSE Event | 触发时机 | data 内容 |
|-----------|---------|-----------|
| `thinking` | Agent 开始推理 / Tool 开始执行 | `"正在分析问题..."` / `"正在生成 SQL..."` / `"正在执行查询..."` |
| `tool_call` | Tool 被调用 | `{tool: "generate_sql", args: {question: "..."}}` |
| `sql` | `generate_sql` 执行完毕 | `{sql: "SELECT ...", sql_hash: "a1b2c3"}` |
| `data` | `execute_sql` 执行完毕 | `{columns, rows, row_count, page, total_pages, has_more, statistics, sql_hash}` |
| `analysis` | `analyze_data` 执行完毕 | `AnalysisOutput` 的 JSON |
| `chunk` | LLM 流式输出文本 | 文本片段 |
| `done` | 图执行结束 | 空 |
| `error` | 任意步骤出错 | 错误信息 |

### 6.2 API 端点实现骨架

```python
@router.post("/stream")
async def bi_stream(req: BIRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    async def event_generator():
        agent = build_bi_agent(db, current_user.id, session_id)
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=req.question)]},
            version="v2"
        ):
            sse_event = convert_langgraph_event(event)
            if sse_event:
                yield sse_event
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 七、多轮对话与会话隔离

### 7.1 Session 管理

- session_id 前缀：`bi_`
- 创建逻辑：前端传入 → 优先使用；无则生成 `bi_{uuid4()}`
- 存储在 `localStorage` 中，跨页面刷新保持
- 历史记录通过 `conversation_dao.get_recent_turns()` 加载（最近 10 轮）

### 7.2 Agent 历史注入

每个请求开始时，从数据库加载该 session 的最近 N 轮对话，转为 LangChain `HumanMessage` / `AIMessage` 列表，作为 `state.messages` 的初始值。这样 Agent 自然地"记住"上下文。

### 7.3 每轮保存

图执行结束后，从 `state` 中提取：
- `question` → 存入 `question` 字段
- `generated_sql` → 存入 `sql_query` 字段
- `query_result` → 存入 `result_summary` 字段（JSON）
- `analysis_result` → 存入 `answer_text` 字段（结构化的 JSON 字符串）
- 最后一条 `AIMessage.content` → 存入 `answer_text` 字段

---

## 八、与现有代码的关系

### 8.1 复用（不动）

| 文件 | 复用内容 |
|------|---------|
| `services/sql_generator.py` | `generate_sql()`, `execute_sql_to_dict()`, `validate_sql()`, `fix_table_names()`, `retrieve_schema_context()` |
| `services/llm_service.py` | `get_llm_client()`, `get_llm_model()`, `get_llm_temperature()` |
| `services/intent_classifier.py` | `sanitize_prompt_input()` — prompt 注入防护 |
| `dao/conversation_dao.py` | `save_turn()`, `get_recent_turns()`, `get_turn_count()` |
| `model/conversation.py` | `ConversationMemory` 表 |

### 8.2 新建

| 文件 | 说明 |
|------|------|
| `services/bi_agent.py` | LangGraph Agent 定义（State, Graph, Tools, System Prompt） |
| `services/bi_analysis.py` | `AnalysisOutput` schema + `with_structured_output()` 封装 |
| `api/bi_agent.py` | `POST /bi/stream` SSE 端点 |
| `static/js/modules/biChat.js` | 前端对话 BI 模块（替代 `chat.js`） |

### 8.3 废弃

| 文件 | 处理方式 |
|------|---------|
| `api/query_agent.py` | 保留文件，所有路由返回 410 Gone + 迁移提示 |
| `services/query_agent_service.py` | 删除（LangGraph Agent 替代） |
| `services/analysis_service.py` | 删除（`analyze_data` Tool 替代） |
| `services/stream_buffer.py` | 删除（LangGraph 流式原生处理） |
| `static/js/modules/chat.js` | 删除（`biChat.js` 替代） |
| `prompts/analysis_prompt.txt` | 删除（prompt 移到 `bi_agent.py` system prompt 中） |
| `prompts/analysis_refine.txt` | 删除 |

### 8.4 修改

| 文件 | 改动 |
|------|------|
| `main.py` | 注册 `bi_agent` 路由；移除 `query_agent` 路由注册 |
| `static/index.html` | "智能问答"Tab 改为"数据对话"；更新 Vue 绑定 |
| `static/js/app.js` | 导入 `biChat` 模块替代 `chat` 模块 |

---

## 九、System Prompt 设计

```markdown
你是「沃林学生管理系统」的 AI 数据分析助手。

## 核心能力
你可以通过以下工具帮助用户：
1. **generate_sql** — 把自然语言问题转为 SQL 查询
2. **execute_sql** — 执行 SQL 并获取结构化结果
3. **analyze_data** — 对查询结果进行数据分析和可视化建议

## 工作流程
- 用户提出数据问题 → 先生成 SQL → 执行查询 → 分析结果
- 用户直接闲聊 → 不调工具，直接回复
- 用户要求分析但未指定数据 → 先查数据再分析

## 重要规则
- 所有表名均为单数（teacher 不是 teachers，stu_basic_info 不是 students）
- 所有查询必须过滤 is_deleted = 0
- 只生成 SELECT 语句
- 生成 SQL 前可以通过 generate_sql 的 context 参数引用之前的查询条件

## 回答风格
- 先给出结论，再展示数据细节
- 如果数据适合图表展示，在分析中给出图表建议
- 使用中文，简洁清晰
```

---

## 十、改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/bi_agent.py` | **新建** | LangGraph Agent：State + Graph + Tools + System Prompt |
| `services/bi_analysis.py` | **新建** | `AnalysisOutput` Pydantic schema + 结构化输出 |
| `api/bi_agent.py` | **新建** | `POST /bi/stream` SSE 端点 |
| `main.py` | 修改 | 注册 bi_agent 路由，移除 query_agent 路由 |
| `static/js/modules/biChat.js` | **新建** | 前端对话 BI 模块 |
| `static/js/app.js` | 修改 | 导入 biChat，移除 chat |
| `static/index.html` | 修改 | Tab 重命名 + Vue 绑定更新 |
| `api/query_agent.py` | 废弃 | 路由返回 410 Gone |
| `services/query_agent_service.py` | 删除 | 被 LangGraph Agent 替代 |
| `services/analysis_service.py` | 删除 | 被 `analyze_data` Tool 替代 |
| `services/stream_buffer.py` | 删除 | LangGraph 流式原生处理 |
| `static/js/modules/chat.js` | 删除 | 被 `biChat.js` 替代 |
| `services/sql_generator.py` | **不动** | 被 Tool 1 & Tool 2 复用 |
| `services/llm_service.py` | **不动** | LLM 客户端复用 |
| `services/intent_classifier.py` | **不动** | 仅复用 `sanitize_prompt_input()` |
| `dao/conversation_dao.py` | **不动** | 会话持久化复用 |
| `model/conversation.py` | **不动** | ORM 模型复用 |

---

## 十一、不再需要的东西

V1 中以下组件在新架构中**不再存在**：

| V1 概念 | 为什么消失 |
|---------|-----------|
| `classify_intent_llm()` 三分支路由 | Agent 自己决定调哪些 Tool，不需要显式意图分类 |
| `check_sql_reference()` | Agent 在多轮对话中自然理解引用关系，不需要单独的检测步骤 |
| `StreamBuffer` | LangGraph `astream_events()` 原生流式 |
| 非流式 `/query/natural` 端点 | 统一走流式 `/bi/stream`，无前端消费者的端点直接砍掉 |
| `use_agent` 配置开关 | 新架构本身就是 Agent，不需要开关 |
| SQL 重试逻辑（手写 80 行） | Agent 自己看到 execute_sql 返回的错误后，自主决定重试 |

---

## 十二、约束与边界

1. **不改 config.json** — 复用现有 LLM 配置（provider/model/api_key/base_url）
2. **不改数据库 schema** — `conversation_memory` 表结构不变
3. **不改 statistics_api** — 如果后续想加预置统计 Tool，直接新增即可
4. **不引入新的 CDN 依赖** — ECharts 已加载，LangChain/LangGraph 是 Python 依赖
5. **LangSmith 可选** — 通过环境变量 `LANGCHAIN_TRACING_V2` 控制，默认关闭
6. **首次实现不包含 vectordb 知识库** — Tool 的 schema 检索直接用 `FALLBACK_SCHEMA`，后续迭代再加

---

## 十三、与旧 P1 Plan 的差异

| 方面 | 旧 Plan (bi-agent-spec.md) | 新 Plan (本文档) |
|------|---------------------------|-------------------|
| Agent 框架 | 手写胶水代码 | **LangGraph StateGraph** |
| Tool 数量 | 2 个（statistics_api + sql_and_query） | **3 个**（generate_sql / execute_sql / analyze_data） |
| Tool 粒度 | SQL 生成+执行合并在一个 Tool | **生成和执行分离**，Agent 可单独调用或串联 |
| 分析输出 | 自由文本 | **Pydantic 结构化输出** (`AnalysisOutput`) |
| 意图分类 | 需要 LLM 意图分类 | **不需要** — Agent 自行决策 |
| 流式方式 | 手写 StreamBuffer | **LangGraph `astream_events()`** |
| 数据分析 | 依赖数据库隐式状态 | **作为独立 Tool，数据从参数传入** |

---

## 十四、验证方法

1. **基础 SQL 查询**："学生有多少人？" → 确认生成 SQL → 执行 → 返回数字
2. **关联查询**："李芳老师有哪些学生？" → 确认 JOIN 多个表
3. **查+分析串联**："查一下五班成绩，分析为什么低分多" → 确认一次对话自动调用 3 个 Tool
4. **纯闲聊**："你好，介绍一下你自己" → 确认不调 Tool，直接文本回复
5. **多轮对话**：第一轮查五班成绩 → 第二轮说"那三班呢？" → 确认 Agent 理解上下文
6. **结构化输出**：任意分析请求 → 确认返回 `AnalysisOutput` 包含 `chart_suggestion`
7. **流式体验**：确认每个 Tool 执行过程和 LLM token 实时推送到前端
8. **会话隔离**：两个不同浏览器 Tab → 确认对话历史不串扰
