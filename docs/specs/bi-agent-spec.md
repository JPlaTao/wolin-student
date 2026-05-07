# P1 — 对话式 BI（替代 query_agent）

> 状态: 待实现 | 优先级: P1 | 预估工时: ~6-8 h

---

## 一、目标

用"对话式 BI"替代现有 `query_agent`，让用户（主要是 teacher/admin）用自然语言请求统计图表，系统自动返回数据并渲染 ECharts 图表。

## 二、核心设计

### 2.1 架构

```
用户输入 "各个班级的平均成绩排名"
       │ SSE POST /bi/stream
       ▼
api/bi_agent.py                     ← 新路由 (prefix="/bi")
       │
       ▼
services/bi_agent.py                ← Agent 编排（意图路由 + Tool 调用）
       │
       ├─ Tool 1: call_statistics_api ──→ 匹配并调用 /statistics/* 端点
       │                                   （9 个预设端点，Agent 匹配问题→端点）
       │
       └─ Tool 2: generate_sql_and_query ──→ 复用 services/sql_generator.py
                                              generate_sql() + execute_sql_to_dict()
```

### 2.2 两个 Tool

**Tool 1 — `call_statistics_api(question: str) → dict`**
- LLM 将问题匹配到预置统计端点（如"平均成绩排名"→`/statistics/advanced/class-avg-score-rank`）
- 后端内部调用对应端点函数，返回结构化数据
- 兜底：匹配不上时返回 null → 走 Tool 2

**Tool 2 — `generate_sql_and_query(question: str) → dict`**
- 复用 `services/sql_generator.generate_sql()` 生成 SQL
- 复用 `services/sql_generator.execute_sql_to_dict()` 执行
- 返回 `{columns: [...], rows: [...], sql: "..."}`

### 2.3 LLM 输出格式

LLM 负责：
1. 判断用户意图 → 选择 Tool 1 还是 Tool 2
2. 根据返回数据，判断图表类型（bar/line/pie/scatter）
3. 生成一句话标题（如"各班平均成绩排名"）
4. 用自然语言解释图表含义

后端将 LLM 输出格式化为：
```json
{
  "chart_type": "bar",
  "title": "各班平均成绩排名",
  "data": {"categories": [...], "series": [...]},
  "explanation": "从图表可以看出，Java2301 班平均分最高..."
}
```

### 2.4 会话记录

- 复用 `conversation_dao` + `ConversationMemory` 表
- session_id 加 `bi_` 前缀隔离
- 记录 `question`、`answer_text`（LLM 文本回复），`result_summary`（存 JSON 数据快照）

### 2.5 前端

- 移除"智能查询"Tab（`index.html` 侧边栏 + `chat.js` 的 `sendQuestion`）
- 新增"数据对话"Tab：左侧对话气泡 + 右侧图表区
- ECharts 已加载（5.5.0 CDN），直接复用
- SSE 事件流：`intent` → `chart_data` → `chunk`（解释文字）→ `done`

## 三、动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/bi_agent.py` | 新建 | Agent 编排 + Tool 定义 + LLM 交互 |
| `api/bi_agent.py` | 新建 | `/bi/stream` SSE 端点 |
| `main.py` | 修改 | 注册 bi_agent 路由 |
| `static/index.html` | 修改 | 移除"智能查询"Tab，新增"数据对话"Tab |
| `static/js/modules/chat.js` | 修改 | 移除 sendQuestion/query 相关，或标记废弃 |
| `static/js/app.js` | 修改 | 移除 query 相关 import/state，新增 bi 模块 |
| `api/query_agent.py` | 标记废弃 | 保留文件不解引用，添加 `raise NotImplementedError` |
| `services/sql_generator.py` | 不动 | 被 Tool 2 复用 |
| `api/statistics_api.py` | 不动 | 被 Tool 1 复用 |

## 四、约束

1. **不改 statistics_api** — 端点/响应格式不变
2. **不改 sql_generator** — 复用现有 `generate_sql()` + `execute_sql_to_dict()`
3. **不改 config.json** — 不新增配置项
4. **不引入 LangChain/LangGraph** — 坚持手写胶水代码
5. **前端不引入新库** — ECharts 已有
6. **SSE 事件格式**与现有流式接口兼容（event: data 格式）

## 五、暂不处理

- LLM 多轮规划（当前仅单轮 Tool 调用）
- 图表类型由用户指定（当前由 LLM 自动判断）
- 图表导出（PNG/SVG）
- 仪表板自定义布局
- vectordb 知识库（向量检索暂不在 P1 使用）

## 六、验证方法

1. 启动服务，登录 admin/teacher 账号
2. 点击"数据对话"Tab
3. 输入"帮我看看各班平均成绩排名" → 确认返回柱状图 + 文字解释
4. 输入"薪资最高的前5个学生是谁" → 确认返回表格/柱状图
5. 输入"Java2301 班所有学生的成绩" → 确认走 Tool 2 动态 SQL
6. 连续两轮对话 → 确认 LLM 能引用前文上下文
