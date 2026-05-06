# QueryAgent 重构 — 交接文档

> 日期: 2026-05-06
> 状态: 重构完成，可正常启动和导入。**未做运行时 API 回归测试**。

---

## 做了什么

按 `docs/specs/query-agent-refactor-spec.md` 完成了全部 7 步重构。

### 改动文件清单

| 文件 | 操作 |
|------|------|
| `api/query_agent.py` | 重写（1408→722 行），仅保留路由 + 编排 |
| `services/llm_service.py` | 新建 — LLM 客户端延迟初始化 |
| `services/intent_classifier.py` | 新建 — 意图分类 + SQL 引用检测 |
| `services/sql_generator.py` | 新建 — SQL 生成 + 验证 + 修复 |
| `services/analysis_service.py` | 新建 — 数据分析 + 闲聊处理 |
| `services/stream_buffer.py` | 新建 — StreamBuffer 纯搬移 |
| `utils/json_encoder.py` | 新建 — SafeJSONEncoder 纯搬移 |
| `prompts/loader.py` | 新建 — Prompt 文件加载器 |
| `prompts/intent_classification.txt` | 新建 |
| `prompts/sql_reference_check.txt` | 新建 |
| `prompts/aggregate_sql.txt` | 新建 |
| `prompts/analysis_refine.txt` | 新建 |
| `prompts/analysis_prompt.txt` | 新建 |

### 未改动的相关文件

- `services/query_agent_service.py` (LangChain Agent 路径)
- `dao/conversation_dao.py`
- `model/*.py`
- `core/*.py`
- `static/` (前端)
- `config.json`

---

## 验证了什么

1. **模块导入**: 所有新/改模块单独 import 通过
2. **main.py 导入**: `import main` 通过
3. **无 import 循环**: 依赖图验证为 DAG
4. **语法检查**: Python 语法无错误

## 未验证的

1. **⚠️ 运行时 API 回归**: 未启动 uvicorn 做实际 HTTP 请求测试。需要验证：
   - `POST /query/stream` SQL 类问题 → `intent/sql/data/done` 事件流
   - `POST /query/stream` 分析类问题 → `intent/chunk/done` 事件流
   - `POST /query/stream` 闲聊 → `intent/chunk/done` 事件流
   - `POST /query/natural` 非流式端点（如果前端还在用）
2. **⚠️ 前端回归**: 未在浏览器打开"智能查询"Tab 做端到端测试
3. **⚠️ pytest**: 未运行 `tests/test_api.py` / `tests/quick_test.py`

---

## 剩余问题（本次未处理）

优先级从高到低：

### P1（建议尽快处理）

1. **运行时回归测试** — 验证上述 API 端点正常工作。若 mock LLM 可用则用 mock，否则用实际 deepseek key
2. **确认 `/natural` 端点是否死代码** — 检查前端代码是否调用了 `POST /query/natural`。如果是，可以删除 `natural_query()` 路由及所有相关辅助函数（约 100 行），进一步精简

### P2

3. **`sql_generator.py` 的 `validate_sql` 三重验证** — 目前仍是黑名单 + 正则 + sqlparse 三层，可以合并精简
4. **`analysis_service.py` 拆分** — 当前的 `process_chat_branch` 放在 analysis 模块中语义不符，可拆为 `services/chat_service.py`

### P3（已知但未规划）

5. **`FALLBACK_SCHEMA` 硬编码** — 应改为从 DAO/Model 自动反射表结构
6. **`_sanitize_prompt_input` 正则注入防护** — 治标不治本，应改为结构化 prompt + 输入隔离
7. **流式/非流式路径合并** — `_stream_*_processing` 与 `natural_query` 中的逻辑高度重复，但涉及 SSE 响应格式，改动较大
8. **`vectordb` 模块级全局状态** — 当前仍是模块级初始化，应改为服务类 + 依赖注入
9. **测试覆盖** — 新增单元测试覆盖 `intent_classifier`、`sql_generator`、`analysis_service` 三个模块

---

## 恢复工作的命令

```bash
cd e:/01-Projects/wolin-student
source .venv/Scripts/activate
python main.py                          # 启动服务
# 在另一个终端：
curl -N http://localhost:8080/query/stream -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"question":"查询所有学生"}'
.venv/Scripts/python -m pytest tests/test_api.py -v   # 跑测试
```
