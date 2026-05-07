# AI Tab 按角色分离 + 角色体系扩展评估

> 状态: 待实现 | 优先级: P2 | 预估工时: ~4-6 h

---

## 一、目标

将当前"一个 AI 聊天给所有人用"的模式，改为按用户角色提供不同的 AI 对话入口：

| 角色 | AI 功能 | 定位 |
|------|---------|------|
| **student** | 黛玉智能（已有） | 情感陪伴、文学辅导、趣味聊天 |
| **teacher** | 智能对话（新建） | 教学助手、专业问答、文档辅助 |
| **admin** | 数据对话（P1 BI Agent） | 自然语言 → 统计图表 |

## 二、当前状态

### 2.1 角色体系

项目当前有三个有效角色：`admin`、`teacher`、`student`（第四个 `"user"` 是 DB 默认值，但不在 `VALID_ROLES` 中，属于死代码）。

```
core/permissions.py:
  ROLE_ADMIN    = "admin"
  ROLE_TEACHER  = "teacher"
  ROLE_STUDENT  = "student"
  VALID_ROLES   = ["admin", "teacher", "student"]
  REGISTRABLE_ROLES = ["student", "teacher"]    # admin 不能自注册
```

### 2.2 当前 AI Tab

| Tab | 路由 | 可见性 | 状态 |
|-----|------|--------|------|
| 黛玉智能 | `/lin_daiyu_agent/*` | 所有人 | 运行中 |
| 智能查询 | `/query_agent/*` | 所有人 | 已废弃，待 P1 BI 替代 |
| 文生图 | `/image_gen/*` | 所有人 | 运行中 |

### 2.3 角色扩展难度评估

添加一个新角色（如 `leader`）需要改动的文件：

| 文件 | 改动 | 工作量 |
|------|------|--------|
| `core/permissions.py` | `VALID_ROLES` 加一个字符串 | 1 行 |
| `model/user.py` | 更新 column comment | 1 行 |
| `api/auth_api.py` | 视情况加入 `REGISTRABLE_ROLES` | 1-2 行 |
| `static/js/modules/auth.js` | `hasRole` 已支持任意角色，无需改动 | 0 行 |
| `static/index.html` | 按需加 `v-if="hasRole('leader')"` | 按需 |

**结论：扩展非常方便。** 但目前 `admin` 已经可以充当"领导"角色使用 BI 功能，不需要立刻加新角色。

## 三、设计方案

### 3.1 前端 Tab 拆分

```
当前:
  黛玉智能 (所有人可见)

目标:
  黛玉智能 (v-if="hasRole('student')")        ← 学生专属
  智能对话 (v-if="hasRole('admin', 'teacher')") ← 教师/管理员
  数据对话 (v-if="hasRole('admin')")           ← P1 BI，替代"智能查询"
```

文生图 Tab 暂保持所有人可见（无明显角色差异需求）。

### 3.2 后端 — 新建 Teacher Agent

新建 `services/teacher_agent.py` + `api/teacher_agent_api.py`，与黛玉 Agent 架构一致：

```
services/teacher_agent.py:
  - System Prompt: 教师助手角色（专业、实用、简洁）
  - 能力：教案建议、学生问题分析、教育政策问答、文档润色
  - Temperature: 0.6（比黛玉低，更确定性的回答）
  - 会话前缀: tah_（teacher agent history）

api/teacher_agent_api.py:
  - POST /teacher-agent/chat       ← 非流式对话
  - POST /teacher-agent/stream     ← SSE 流式对话
  - 认证: get_current_user + require_role(["admin", "teacher"])
```

### 3.3 前端模块

新建 `static/js/modules/teacherAgent.js`，复用 daiyu.js 的对话组件模式。两种方案：

**方案 A — 复制 daiyu.js 改造**（快，但重复代码）
**方案 B — 抽取通用 chat-engine.js**（干净，但多一步抽象）

建议方案 B：从 `daiyu.js` 中抽取一个 `createChatEngine(config)` 工厂函数，黛玉和教师助手都是该工厂的实例。

```javascript
// 抽取后的通用引擎
function createChatEngine({ apiBase, personaName, greeting, theme }) {
    // 消息列表、发送、流式接收、Markdown 渲染
    return { messages, input, send, clear, loading };
}

// 黛玉
const daiyu = createChatEngine({
    apiBase: '/lin-daiyu-agent',
    personaName: '林黛玉',
    greeting: '这位小友好。我是颦儿...',
    theme: 'purple',
});

// 教师助手
const teacherAgent = createChatEngine({
    apiBase: '/teacher-agent',
    personaName: '教学助手',
    greeting: '你好，有什么教学相关的问题我可以帮你？',
    theme: 'blue',
});
```

### 3.4 改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/teacher_agent.py` | 新建 | 教师助手 System Prompt + LLM 调用 |
| `api/teacher_agent_api.py` | 新建 | 教师助手 API 路由 |
| `main.py` | 修改 | 注册 teacher_agent 路由 |
| `static/js/modules/chat-engine.js` | 新建 | 通用聊天引擎（从 daiyu.js 抽取） |
| `static/js/modules/daiyu.js` | 修改 | 改为调用 chat-engine 工厂 |
| `static/js/modules/teacherAgent.js` | 新建 | 教师助手模块（调用 chat-engine 工厂） |
| `static/js/app.js` | 修改 | 导入 teacherAgent 模块，暴露给模板 |
| `static/index.html` | 修改 | 拆分 Tab 可见性 + 新增教师助手 Tab 面板 |

## 四、约束

1. **不改 config.json**
2. **黛玉 Tab 不 break** — 学生用户体验不变
3. **会话隔离** — 黛玉和教师助手使用不同的 session_id 前缀
4. **教师助手先做非流式，稳定后加流式** — 与黛玉开发路径一致
5. **文生图暂不拆分** — 所有角色都能用，无角色差异需求

## 五、暂不处理

- 新角色（`leader`/`principal`）— `admin` 已能满足 BI 需求
- 教师助手的 RAG 知识库集成 — 后续迭代
- 教师助手的历史记录管理 — 与黛玉共用同一套 conversation_dao 逻辑

## 六、验证方法

1. 学生登录 → 侧边栏只有"黛玉智能"，无"智能对话"
2. 教师/管理员登录 → 侧边栏显示"智能对话"（黛玉智能对学生隐藏）
3. 教师使用"智能对话" → 确认回答风格专业、实用
4. 切换 Tab → 确认会话独立，不清空对方的消息
5. 学生端黛玉功能完全正常（回归测试）
