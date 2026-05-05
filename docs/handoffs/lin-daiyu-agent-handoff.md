# 林黛玉 Agent — 轮次交接

## 本轮目标

基于"学生管理系统"的现有 AI 能力（LLM 对话、会话记忆、SSE 流式输出），实现一个以林黛玉为人设的性格化聊天 Agent。

## 完成项

### 新增文件

**`services/lin_daiyu_service.py`** — 人设提示词 + LLM 调用层
- `DAIYU_SYSTEM_PROMPT`：核心人设提示词（~1323 字），涵盖身份定位、语言风格（半文半白）、性格特征（才情卓绝/敏感细腻/清高孤傲）、学业辅助能力、情绪陪伴方法、行为约束
- `DAIYU_GREETING`：固定开场问候语
- `_get_api_key()`：根据 `config.json` 的 provider 获取 API key
- 模块级 `client = AsyncOpenAI(...)`：独立的 LLM 客户端实例（与 query_agent 解耦）
- `_format_history_turns()`：将 ConversationMemory 转为 OpenAI 消息格式
- `build_conversation_messages()`：构建完整 messages 数组（system + history + user）
- `generate_response()`：异步调用 LLM 生成回复，temperature=0.85

**`api/lin_daiyu_agent.py`** — FastAPI 路由与端点
- `DaiyuChatRequest` / `DaiyuChatResponse` Pydantic 模型
- `POST /api/daiyu/chat`：非流式对话
- `POST /api/daiyu/stream`：SSE 流式对话（事件：`chunk`, `done`, `error`）
- session_id 使用 `ldy_` 前缀隔离（如 `ldy_user_42_xxxx`）
- 复用 `dao/conversation_dao.py`（save_turn, get_recent_turns, get_turn_count）

### 修改文件

| 文件 | 改动 |
|------|------|
| `main.py` | 导入 `lin_daiyu_agent` 并注册 `app.include_router(lin_daiyu_agent.router)` |
| `static/index.html` | 侧边栏新增"黛玉智能"Tab（`fa-feather-alt` 图标，位于智能问答与高级统计之间）；新增聊天面板（紫粉渐变头部、古风签名、紫色输入框） |
| `static/js/app.js` | 新增 daiyuMessages/daiyuQuestion/daiyuStreaming/daiyuChatContainer 状态；新增 sendDaiyuQuestion SSE 流式函数；scrollDaiyuToBottom 辅助函数；所有新 ref/fn 加入 return |
| `static/css/style.css` | 新增 `.daiyu-bubble` class（淡紫粉渐变背景，紫色边框） |

## 架构

```
static/index.html + static/js/app.js    ← 新 Tab "黛玉智能"
       │ POST /api/daiyu/stream
       ▼
api/lin_daiyu_agent.py                  ← FastAPI Router (prefix="/api/daiyu")
       ▼
services/lin_daiyu_service.py           ← 系统提示词 + LLM 调用
       ▼
dao/conversation_dao.py                 ← 复用现有 save_turn / get_recent_turns
model/conversation.py                   ← 复用现有 ConversationMemory 表
```

## 关键设计决策

1. **会话隔离**：session_id 加 `ldy_` 前缀，避免与 query_agent 交叉
2. **LLM 独立实例**：在 service 层创建独立的 `AsyncOpenAI` 客户端，与 query_agent 解耦
3. **对话记忆复用**：直接复用 `ConversationMemory` 表，不建新表不加字段
4. **temperature**：显式传 0.85（略高于默认 0.7），更适合创意性人设回复
5. **系统提示词不下沉**：每次请求重新发送 system prompt，不存入 conversation_memory 表

## 验证结果

- `POST /api/daiyu/chat`：正常返回林黛玉风格半文半白回复 ✅
- `POST /api/daiyu/stream`：SSE 流式 `chunk`/`done`/`error` 事件正常 ✅
- 人设一致性：引用诗句（如"少年心事当拏云"）、古风称谓（"这位同学""小友"）、大观园背景回忆、共情式回应 ✅
- 前端 Tab：可点击，聊天面板可交互，流式内容实时渲染 ✅
- 会话记忆：连续对话正常，session_id 带 `ldy_` 前缀 ✅

## 关键文件清单

| 文件 | 性质 |
|------|------|
| `services/lin_daiyu_service.py` | 核心 — 人设提示词 + LLM 调用 |
| `api/lin_daiyu_agent.py` | 核心 — API 端点 |
| `main.py` | 修改 — 路由注册 |
| `static/index.html` | 修改 — 前端 Tab + 面板 |
| `static/js/app.js` | 修改 — 前端逻辑 |
| `static/css/style.css` | 修改 — 气泡样式 |
| `docs/specs/lin-daiyu-agent-spec.md` | 文档 — 需求分析与架构设计 |

## 遗留 / 暂不处理

以下可选功能记录在 `docs/二阶段项目需求.md`，本期未实现：

- 期末评语生成器
- 学生违纪话术教练
- 班级公告润色助手
- 简易 RAG：校规问答机器人（RAG 入门版，直接把校规文本塞 Prompt）
- 成绩波动诊断书
- 班会活动策划师
- 模拟面试官（多轮对话入门）
- 智能分班/分组助手
