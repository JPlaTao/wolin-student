# 林黛玉 Agent — 需求分析与架构设计

> 状态: 已完成 (2026-05-05) | 优先级: P2 | 预估工时: ~6 h

## Context

基于"学生管理系统"的现有 AI 能力（LLM 对话、会话记忆、SSE 流式输出），实现一个以**林黛玉**为人设的性格化聊天 Agent。需求来源于 `docs/二阶段项目需求.md`，核心特点是半文半白的语言风格、诗词鉴赏/文学辅导能力、以及具有古典韵味的情绪陪伴。

## 需求范围

**本期实现：**
1. 林黛玉角色聊天（Persona Agent）—— 核心功能
2. 系统提示词工程（半文半白、诗词典故、敏感细腻、偶尔菱角）
3. 多轮对话记忆（复用现有 `ConversationMemory` 模型）
4. SSE 流式输出
5. 前端独立聊天 Tab + 紫色/古风主题 UI

**本期不实现（可选功能）：**
- 期末评语生成器、违纪话术教练、公告润色、校规 RAG、成绩诊断、班会策划、模拟面试、分组助手

## 架构设计

```
static/index.html + static/js/app.js    ← 新 Tab "黛玉智能"
       │ POST /api/daiyu/stream
       ▼
api/lin_daiyu_agent.py                  ← FastAPI Router (prefix="/api/daiyu")
       ▼
services/lin_daiyu_service.py           ← 系统提示词 + LLM 调用 + 对话构建
       ▼
dao/conversation_dao.py                 ← 复用现有 save_turn / get_recent_turns
model/conversation.py                   ← 复用现有 ConversationMemory 表
```

### 关键设计决策

1. **会话隔离**：session_id 加 `ldy_` 前缀（如 `ldy_user_42_xxxx`），避免与 query_agent 的会话交叉
2. **LLM 复用**：在 `services/lin_daiyu_service.py` 中创建独立的 `AsyncOpenAI` 实例（与 query_agent 解耦），使用相同的 `settings.llm` 配置
3. **对话记忆复用**：直接复用 `ConversationMemory` 表和 `dao/conversation_dao.py`，不建新表、不加字段
4. **temperature**：显式传 0.85（略高于默认 0.7），更适合创意性人设回复

## 需要修改/新增的文件

### 1. 新增 `services/lin_daiyu_service.py`
- `DAIYU_SYSTEM_PROMPT` — 核心人设系统提示词（约 1200 字中文）
- `_get_api_key()` — 获取 API key
- 模块级 `client = AsyncOpenAI(...)` — LLM 客户端
- `_format_history_turns()` — 将 ConversationMemory 转为 OpenAI 消息格式
- `build_conversation_messages()` — 构建完整的 messages 数组（system + history + user）
- `generate_response()` — 异步调用 LLM 生成回复

### 2. 新增 `api/lin_daiyu_agent.py`
- `DaiyuChatRequest(BaseModel)` — `{question, session_id?}`
- `DaiyuChatResponse(BaseModel)` — `{session_id, turn_index, answer}`
- `POST /api/daiyu/chat` — 非流式对话
- `POST /api/daiyu/stream` — SSE 流式对话（事件: `chunk`, `done`, `error`）
- 两个端点都通过 `Depends(get_current_user)` 认证
- 从 `dao/conversation_dao` 导入 `get_recent_turns`, `get_turn_count`, `save_turn`

### 3. 修改 `main.py`
- 在 import 块添加 `lin_daiyu_agent`
- 在 include_router 块添加 `app.include_router(lin_daiyu_agent.router)`

### 4. 修改 `static/index.html`
- 侧边栏导航新增一个 Tab（在"智能问答"和"文生图片"之间）：
  ```html
  <a @click.prevent="activeTab = 'daiyu'" ...>
      <i class="fas fa-feather-alt w-5"></i>
      <span v-show="!sidebarCollapsed">黛玉智能</span>
  </a>
  ```
- 新增主内容区 `v-if="activeTab === 'daiyu'"`：
  - 头部渐变背景（紫→粉）+ 角色名 + 签名诗句
  - 聊天消息列表（复用现有 chat bubble 样式，AI 消息用 `daiyu-bubble` class）
  - 底部输入框 + 发送按钮

### 5. 修改 `static/js/app.js`
- 新增响应式状态：
  - `daiyuMessages` (ref array, 初始含 AI 问候语)
  - `daiyuQuestion` (ref string)
  - `daiyuStreaming` (ref boolean)
  - `daiyuChatContainer` (ref null)
- 新增 `sendDaiyuQuestion()` 函数（参照 `sendQuestion` 的 SSE 读取逻辑，但简化——无需 intent/sql/data 事件处理，只处理 `chunk` + `done` + `error`）
- 所有新 ref/fn 加到 `return` 对象

### 6. 修改 `static/css/style.css`
- 新增 `.daiyu-bubble` class (淡紫粉渐变背景，紫色边框，与默认 chat bubble 区分)

## 实现步骤

```
Step 1: services/lin_daiyu_service.py    ← 人设提示词 + LLM 调用（独立可测）
Step 2: api/lin_daiyu_agent.py           ← API 端点
Step 3: main.py                          ← 注册路由
Step 4: static/index.html                ← 前端 Tab + 聊天面板
Step 5: static/js/app.js + style.css     ← 前端逻辑 + 样式
```

## 系统提示词设计要点

- **身份定位**：林黛玉穿越到现代，以 AI 形态与学生对话
- **语言风格**：半文半白，善用诗词典故，自称"我"/"颦儿"，称呼"这位同学"/"小友"
- **性格特征**：才情卓绝、敏感细腻、清高孤傲、"怼人"艺术
- **学业辅助**：诗词对答、文学点评（侧重情感/意境而非结构分析）
- **情绪陪伴**：先共情（典雅语言）→ 再开解（诗词/人生感悟）→ 最后温和建议
- **行为约束**：禁网络用语、保持一致性、超出范围时委婉拒绝
- **开场白**：固定问候语 "这位小友好。我是颦儿..."

## 验证方法

1. 启动服务：`.venv/Scripts/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080`
2. Swagger 验证：`POST /api/daiyu/chat` 发送问题，确认用林黛玉风格回复
3. 流式验证：`POST /api/daiyu/stream` 确认 SSE 事件流正常
4. 前端验证：访问页面 → 登录 → 点击"黛玉智能" Tab → 输入问题 → 确认流式渲染+古风风格
5. 会话记忆验证：连续对话，确认 LLM 能引用前文
