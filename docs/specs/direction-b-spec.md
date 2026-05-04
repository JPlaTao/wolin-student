# 方向 B 最小 Spec：用 LangChain Agent + Tools 重构 SQL 查询链路

## 一、目标

将 `api/query_agent.py` 中**手写的 SQL 生成 + 校验 + 执行 + 重试**循环，替换为 **LangChain AgentExecutor + Tools** 模式。目的是通过最小化改动，掌握 LangChain 最核心的 Agent 和 Tool 抽象。

## 二、范围（只改这些）

### 2.1 新建文件

**`services/query_agent_service.py`** — 包含：

1. **Tool 定义**（3 个）：
   - `retrieve_schema_tool` — 从 Chroma 向量库检索表结构，兜底返回 `FALLBACK_SCHEMA`
   - `execute_readonly_sql_tool` — 接收 SQL → 验证（复用现有 `validate_sql`）→ 执行 → 返回结果字典列表
   - `retrieve_knowledge_tool` — 从 Chroma 向量库检索文档知识

2. **Agent Prompt** — 系统提示词，指导 Agent 使用上述工具生成并执行 SQL：
   - 只生成 SELECT
   - 必须过滤 is_deleted
   - 表名单数
   - 执行失败时自行修正重试

3. **LangChain AgentExecutor** — 使用 `create_openai_tools_agent` + `AgentExecutor`，LLM 后端复用现有的 `ChatOpenAI`（对接 Kimi/DeepSeek/OpenAI）

4. **入口函数** `async def agent_sql_query(question, session_id, db) -> dict`：
   - 输入：用户问题
   - 内部：Agent 自行规划 → 检索 schema → 生成 SQL → 执行 → 修正（如需）
   - 输出：`{ sql, data, count }`（保持与现有响应格式兼容）

### 2.2 修改文件

**`api/query_agent.py`** — 只改 SQL 意图分支（约 30 行）：

- 在 `natural_query()` 的 `if intent == "sql":` 分支中，**新增一条路径**：
  ```python
  if intent == "sql":
      # 新路径：LangChain Agent
      result = await agent_sql_query(question, session_id, db)
      # ... 复用现有的 save_turn、响应构建 ...
  ```
- 原手写路径保留作为兜底（通过配置开关控制，默认走 Agent）

**`requirements.txt`** — 添加 `langchain-openai>=0.1.0`

### 2.3 保持不变的部分

| 模块 | 不变原因 |
|---|---|
| 意图分类（`classify_intent_llm`） | 工作正常，且与 Agent 无关 |
| 闲聊分支（chat） | 无需 Agent |
| 分析分支（analysis） | 无需 Agent |
| 流式端点（`/query/stream`） | 本次不改，Agent 模式暂不支持流式 |
| 对话记忆 DAO（`conversation_dao`） | Agent 执行结果仍通过原 DAO 持久化 |
| 前端 | 无改动 |
| API 路由注册 | 无改动 |
| 配置系统 | 无改动 |

## 三、约束

1. **LLM 客户端复用现有配置** — Agent 内部使用 `ChatOpenAI(model=llm_config.model, api_key=..., base_url=...)`，不引入新模型或新密钥
2. **SQL 安全验证不降级** — `execute_readonly_sql_tool` 内部必须调用现有的 `validate_sql()`，与手写路径使用相同的安全策略
3. **响应格式兼容** — Agent 的最终输出必须能接入现有的 `_build_sql_result_response()` / `save_turn()` / `_execute_and_save_sql()` 体系
4. **故障兜底** — 如果 Agent 执行失败（Tool 调用异常、LLM 超时等），抛 `HTTPException 500`，由外层全局异常处理器统一处理
5. **不删除现有代码** — 手写路径通过 `config.json` 中 `llm.use_agent: bool` 控制切换，默认关闭，确保零风险上线

## 四、不处理项（显式排除）

| 事项 | 原因 |
|---|---|
| 流式响应中支持 Agent | 涉及 SSE 与 Agent 中间状态的复杂映射，超出最小范围 |
| Agent 的记忆（Memory） | 现有 `conversation_dao` 方案已满足需求 |
| LangSmith Tracing | 需要额外配置账号，不是 LangChain 核心学习目标 |
| `create_sql_agent` 高阶封装 | 学习目的优先理解底层 Tool + AgentExecutor 机制 |
| 多 Tool 复杂规划 | 本次 Agent 只需 3 个 Tool，顺序确定，不需要复杂 ReAct 循环 |
| 前端改动 | API 响应格式不变，前端无感知 |
| 测试覆盖 | 本次不新增测试文件，手动验证 |

## 五、学习要点（做这个过程中会学到）

1. `ChatOpenAI` 的实例化和与 LangChain 的集成
2. `@tool` 装饰器定义 Tool（带参数类型注解）
3. `create_openai_tools_agent` 的 prompt 构造
4. `AgentExecutor` 的执行循环和错误处理
5. Agent 中间步骤的观察（`return_intermediate_steps=True`）
6. Tool 内部调用现有业务代码的正确姿势

## 六、验证方式

```bash
# 1. 启动服务
python main.py

# 2. 用已存在的 POST /query/natural 验证
#    请求体增加字段 {"use_agent": true}
#    或通过 config.json 中 llm.use_agent: true 全局切换

# 3. 测试用例：
#    - "查询所有学生" → 应生成 SELECT + 执行 + 返回数据
#    - "每个班级的平均成绩" → 应生成聚合 SQL
#    - "薪资最高的5个人" → 应排序 + LIMIT
#    - "删除学生表" → Agent 应拒绝生成（Tool 层 validate_sql 拦截）

# 4. 回归测试
pytest tests/test_api.py -v
```

## 七、预计改动量

| 文件 | 操作 | 行数 |
|---|---|---|
| `services/query_agent_service.py` | **新建** | ~150 行 |
| `api/query_agent.py` | 修改 SQL 分支 + 添加配置读取 | ~30 行 |
| `requirements.txt` | 添加一行 | +1 行 |
| `config.example.json` | 添加 `llm.use_agent` 字段 | +1 行 |
| **合计** | | **~180 行** |
