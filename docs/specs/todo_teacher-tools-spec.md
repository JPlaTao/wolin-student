# P2 — 教师实用工具

> 状态: 待实现 | 优先级: P2 | 预估工时: ~3-4 h

---

## 一、目标

实现三个教师日常工作中最实用的 AI 辅助工具：公告润色、成绩诊断、期末评语。

**开发模式**: 前后端分离并行开发。后端 Agent 和前端 Agent 同时基于本 spec 在独立 worktree 中实现，以 API spec 为契约。

---

## 二、API 接口规范（前后端契约）

所有工具共用：
- **前缀**: `/tools`
- **Auth**: `require_role(["admin", "teacher"])`
- **响应格式**: 统一 `ResponseBase(code=200, data={...})`
- **错误格式**: 标准异常 `NotFoundException` / `ValidationException`，由全局异常处理器序列化
- **非流式**: POST → 同步返回

---

### 2.1 公告润色

```
POST /tools/polish-notice
```

**Request**:
```json
{
    "text": "明天大扫除，大家带抹布，别迟到",
    "style": "formal"
}
```

`style` 枚举: `"formal"`（正式风）| `"humorous"`（幽默风）| `"warm"`（亲切风），默认 `"formal"`

**Response 200**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "polished": "关于教室大扫除的通知\n\n各位同学：\n\n为营造整洁舒适的学习环境，定于明日放学后开展教室大扫除。请各位同学自备抹布等清洁工具，准时参加。\n\n特此通知。\n\nXX班 班主任\n2026年5月8日"
    }
}
```

**Error**: 无特殊错误（text 非空由 Pydantic 校验）

**System Prompt**:
```
你是学校行政秘书。请将用户输入的草稿改写为一份{style}的通知。
{style_map}
要求：格式规范，语气得体，重点突出，包含标题、正文、落款。
```

`style_map`:
- formal → "风格要求：正式、规范、书面化。"
- humorous → "风格要求：幽默、轻松、有创意，可以适当用梗。"
- warm → "风格要求：亲切、温和、口语化，像朋友间说话。"

---

### 2.2 成绩诊断

```
POST /tools/diagnose-score
```

**Request**:
```json
{
    "stu_id": 1
}
```

**Response 200**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "stu_name": "张三",
        "class_name": "高三(1)班",
        "exam_records": [
            {"seq_no": 1, "grade": 85.0, "exam_date": "2026-03-01"},
            {"seq_no": 2, "grade": 92.0, "exam_date": "2026-04-01"},
            {"seq_no": 3, "grade": 78.0, "exam_date": "2026-05-01"}
        ],
        "analysis": "该生成绩呈现先升后降的趋势。第2次考试进步明显（+7分），但第3次退步较大（-14分），需关注近期学习状态。从数据看，该生有一定潜力，但成绩稳定性不足。建议：1. 分析退步原因；2. 巩固优势科目；3. 制定阶段性目标。"
    }
}
```

**Error**:
- `NotFoundException` — stu_id 不存在或无成绩记录，detail: `"未找到该学生的成绩记录"`

**实现逻辑**:
1. 调用 `exam_dao.exam_get(stu_id=stu_id, seq_no=None, db=db)` 获取学生所有成绩
2. 如果返回空列表 → raise `NotFoundException`
3. 取 `stu_name`、`class_name`（从第一条 exam 记录获取）
4. 将 `exam_records` 传给 LLM 分析
5. 返回 exam_records + analysis 文本

**System Prompt**:
```
你是一位数据分析师兼班主任。分析用户提供的学生成绩列表（按时间顺序，seq_no 表示第几次考试）。
1. 指出哪科进步最大；
2. 指出哪科退步明显；
3. 给出一句针对性的鼓励建议。

注意：
- 当前只有一个科目的成绩（grade 字段），所以主要分析成绩的趋势变化
- 用数字说话（进步/退步了多少分）
- 语气要温和、有建设性
```

---

### 2.3 期末评语生成

```
POST /tools/generate-comment
```

**Request**:
```json
{
    "keywords": "调皮、数学好、爱打架"
}
```

**Response 200**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "comment": "你是个头脑灵活的孩子，数学课上总能快速找到解题思路，这一点非常难得。不过，有时候你的精力用错了地方，和同学发生争执不仅会影响友谊，也会让老师为你担心。老师相信，如果你能把数学上的聪明劲用在处理人际关系上，一定会成为一个更受欢迎的人。期待看到你温和待人、自律自强的那一天！"
    }
}
```

**Error**: 无特殊错误

**System Prompt**:
```
你是一位拥有20年经验的资深班主任。请根据用户提供的学生特点关键词，写一段100字左右的期末评语。

要求：
1. 语气亲切，使用"三明治沟通法"（先表扬优点，再委婉提出缺点，最后给予期望）
2. 多用成语
3. 避免"希望你以后..."这类死板句式
4. 评语要具体，能看出是针对该生特点写的，而不是通用模板
```

---

## 三、前后端责任边界

### 后端 Agent（worktree: `feature/teacher-tools-api`）

**只动这些文件**:
| 文件 | 操作 | 说明 |
|------|------|------|
| `api/tools_api.py` | 新建 | 3 个 POST 端点 |
| `services/tools_service.py` | 新建 | Prompt 构建 + LLM 调用（基于 `get_llm_client()`） |
| `schemas/tools_schemas.py` | 新建 | Pydantic request/response schema 定义 |
| `main.py` | 修改 | 注册 `tools.router` |

**不动**: `static/`、`dao/`(已存在)、`config.json`、`core/`、`model/`

### 前端 Agent（worktree: `feature/teacher-tools-ui`）

**只动这些文件**:
| 文件 | 操作 | 说明 |
|------|------|------|
| `static/index.html` | 修改 | 侧边栏加"教师工具"nav item + 三工具卡片模板 |
| `static/js/modules/tools.js` | 新建 | 三个工具的交互逻辑 + mock 数据 |
| `static/js/app.js` | 修改 | 导入 `createToolsModule` + 模板绑定 |

**不动**: `api/`、`services/`、`dao/`、`core/`

### Mock 数据约定

前端在 `tools.js` 中内置 mock 数据，格式与真实 API 响应完全一致：

```javascript
// 公告润色 mock
const MOCK_POLISH = {
    code: 200,
    data: {
        polished: "关于教室大扫除的通知\n\n各位同学：\n\n为营造整洁舒适的学习环境..."
    }
};

// 成绩诊断 mock
const MOCK_DIAGNOSE = {
    code: 200,
    data: {
        stu_name: "张三",
        class_name: "高三(1)班",
        exam_records: [
            { seq_no: 1, grade: 85.0, exam_date: "2026-03-01" },
            { seq_no: 2, grade: 92.0, exam_date: "2026-04-01" },
            { seq_no: 3, grade: 78.0, exam_date: "2026-05-01" }
        ],
        analysis: "该生成绩呈现先升后降的趋势..."
    }
};

// 期末评语 mock
const MOCK_COMMENT = {
    code: 200,
    data: {
        comment: "你是个头脑灵活的孩子..."
    }
};
```

前端先使用 mock 渲染，后端完成后切换为真实 `fetch()` 调用。

---

## 四、前端模板结构

### 4.1 导航

侧边栏新增 nav item（插入在"文生图"和"发送邮件"之间）：

```html
<a
    v-if="hasRole('admin', 'teacher')"
    href="#"
    @click.prevent="activeTab = 'teacherTools'"
    :class="['flex items-center gap-3 px-4 py-3 rounded-xl...', activeTab === 'teacherTools' ? 'app-nav-item-active' : '']"
>
    <i class="fas fa-chalkboard-teacher w-5"></i>
    <span v-show="!sidebarCollapsed">教师工具</span>
</a>
```

### 4.2 Tab 内容区

```
activeTab === 'teacherTools' 时渲染:

┌─────────────────────────────────────────────────┐
│  教师实用工具                                    │
│  AI 辅助教学小工具                                │
├─────────────────────────────────────────────────┤
│ ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│ │ 📝 公告润色   │  │ 📊 成绩诊断   │  │ ⭐ 期末  │ │
│ │ 通知草稿→正   │  │ 学生成绩趋势  │  │ 评语    │ │
│ │ 式/幽默/亲切  │  │ 分析+AI点评  │  │ 关键    │ │
│ │              │  │              │  │ 词→评语 │ │
│ │ [输入框]     │  │ [学生下拉]   │  │ [输入   │ │
│ │ [风格下拉]   │  │ [生成]       │  │ 框]    │ │
│ │ [生成]       │  │ ──────────   │  │ [生成]  │ │
│ │ ──────────   │  │ 折线图+评语  │  │ ──────  │ │
│ │ 结果预览区   │  │              │  │ 评语    │ │
│ └──────────────┘  └──────────────┘  └─────────┘ │
└─────────────────────────────────────────────────┘
```

三个卡片用 CSS grid `grid-cols-1 lg:grid-cols-3` 布局，每个卡片包含：
- 图标 + 标题 + 简短描述
- 输入区域（textarea / 下拉选择 / input）
- 生成按钮（loading 态）
- 结果预览区（生成后显示）

---

## 五、合并顺序

1. **后端先合并** — feature/teacher-tools-api → master（让真实 API 可用）
2. **前端再合并** — feature/teacher-tools-ui → master（把 mock 换成真实调用）
3. **联调** — 验证端到端

---

## 六、验证方法

1. 启动服务，登录 teacher 或 admin 账号
2. 侧边栏出现"教师工具"nav item（student 角色看不到）
3. 公告润色：输入"明天大扫除，大家带抹布"→ 选择"正式风"→ 输出格式化通知
4. 成绩诊断：选择一个学生（已有成绩的）→ 查看折线图 + AI 评语
5. 期末评语：输入"调皮、数学好、爱打架"→ 生成三明治式评语
6. 切换风格（幽默/亲切）→ 输出风格明显不同

---

## 七、约束

1. **复用 LLM 客户端** — 用 `services/llm_service.py` 的 `get_llm_client()`
2. **不改 DAO** — 诊断书调用现有 `exam_dao.exam_get(stu_id, seq_no=None, db)`
3. **不改 config.json**
4. **非流式** — 所有工具都是 POST → 同步返回
