# 方向 B 复盘总结

> 状态: 已完成 (2026-05-04) | 类型: 复盘文档

> LangChain Agent + Tools 重构 SQL 查询链路  
> 实现日期: 2026-05-04  
> 开发者: Claude Code + 人工验证

## 概览

将 `api/query_agent.py` 中手写的 SQL 生成 → 校验 → 执行 → 重试循环，替换为 LangChain AgentExecutor + 3 个 Tool 模式。通过 `llm.use_agent` 配置开关控制，旧路径保留为兜底。

## 改动清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `services/query_agent_service.py` | **新建** (~160 行) | 3 个 Tool + `create_agent` + 入口函数 |
| `api/query_agent.py` | 修改 (+35 行) | SQL 分支插入 Agent 路径 + `use_agent` 请求字段 |
| `core/settings.py` | 修改 (+1 行) | `LLMConfig` 加 `use_agent: bool` |
| `config.json` | 修改 (+1 行) | `llm.use_agent: false` |
| `config.example.json` | 修改 (+1 行) | 同上，供新开发者参考 |
| `requirements.txt` | 修改 (+1 行) | 添加 `langchain-openai` |

## 关键决策

### 1. LangChain 1.x API 适配（偏离原 Spec）

**原 spec** 基于 LangChain 0.1.x，使用 `AgentExecutor` + `create_openai_tools_agent`。  
**实际情况**: 项目环境中实际安装的是 LangChain 1.x（`langchain-classic`），此版本中：
- `AgentExecutor` 和 `create_openai_tools_agent` **已被移除**
- 替代方案: `create_agent`（基于 LangGraph 的 StateGraph）
- `@tool` 装饰器仍在 `langchain.tools` 中，async 支持良好

**应对**: service 文件改写为 `create_agent(model, tools, system_prompt=...)` 模式，LangGraph 状态通过 `messages` 键传递。

### 2. 结果捕获策略

由于 LangChain 1.x 的 Agent 返回的是 LangGraph 状态（`messages` 列表），提取结构化 SQL/数据不如旧版 `return_intermediate_steps` 直观。采用 **`result_store` 闭包方式**:
- 在 `agent_sql_query()` 中创建空 dict `result_store = {}`
- 通过 `_create_tools(db, result_store)` 注入到 `execute_readonly_sql` 工具内部
- 工具执行成功后将 `sql_fixed` 和 `data` 写入 `result_store`
- Agent 执行完毕后从 `result_store` 提取

### 3. 循环依赖规避

`api/query_agent.py` 需要 import `agent_sql_query`，同时 service 中的 Tool 需要引用 `api/query_agent` 的函数（`vectordb`、`FALLBACK_SCHEMA`、`validate_sql` 等）。  
**应对**: service Tool 函数体内部使用延迟导入（`from api.query_agent import xxx`），确保在模块加载时不会互相阻塞。

### 4. SQL 执行路径（不复用 execute_sql_to_dict）

`api/query_agent.execute_sql_to_dict()` 在 SQL 验证失败时抛 `HTTPException`，而 Tool 需要将错误以字符串形式返回给 Agent 使其有机会重试。  
**应对**: Tool 内直接调用 `validate_sql()` + `db.execute(text(sql))`，错误以字符串返回。

## 测试结果

| 用例 | 状态 | 说明 |
|---|---|---|
| "查询所有学生" | ✅ | 生成 `SELECT * FROM stu_basic_info WHERE is_deleted = 0`，返回 48 行 |
| "每个班级的平均成绩" | ✅ | 生成 JOIN + GROUP BY + AVG 聚合查询，返回 9 行 |
| "删除学生表" | ✅ | Agent 拒绝生成 SQL，安全拦截生效 |
| "薪资最高的5个人" | 未测试 | 理论上走通（ORDER BY + LIMIT） |

## 已知问题

### 1. Kimi K2.5 与 LangChain tool calling 不兼容
`kimi-k2.5` 作为 Reasoner 模型，在 tool call 消息中需要 `reasoning_content` 字段，但 LangChain 的 ChatOpenAI 适配器不发送此字段，导致 API 400 错误。  
**当前绕过**: 使用 DeepSeek（`deepseek-chat`）或其他非 Reasoner 模型。

### 2. Agent 路径额外延迟
Agent 的 ReAct 循环至少需要 2-3 次 LLM 调用（规划 → 检索 schema → 生成 SQL → 执行 → 总结），比手写单次生成慢约 2-3 倍。  
**影响**: `query_agent_service.py` 中 `max_iterations=5` 和 `max_execution_time=60` 限制了最坏情况。

### 3. DDL 拦截的错误信息
Agent 拒绝 DDL 时不会调用 `execute_readonly_sql`，导致 `result_store` 为空，返回 500 "Agent 未能生成有效的 SQL 查询"。安全上正确但用户体验不友好。  
**改进方向**: 捕获此场景返回 400 提示 "无法生成查询：您的请求可能包含不被允许的操作"。

## 配置

```json
{
  "llm": {
    "use_agent": false,     // true=LangChain Agent, false=手写路径
    "provider": "deepseek", // kimi / deepseek / openai
    "model": "deepseek-chat",
    "base_url": "https://api.deepseek.com"
  }
}
```

请求级别覆盖: 传 `{"use_agent": true}` 到 POST `/query/natural` 可临时切换，不影响全局配置。
