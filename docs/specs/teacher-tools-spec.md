# P2 — 教师实用工具

> 状态: 待实现 | 优先级: P2 | 预估工时: ~3-4 h

---

## 一、目标

实现三个教师日常工作中最实用的 AI 辅助工具：公告润色、成绩诊断、期末评语。

## 二、三个工具

### 2.1 公告/通知润色助手

**场景**：老师写的通知太口语化，需要改成正式/得体的格式。

**输入**：`草稿文本` + `风格选择（正式/幽默/亲切）`

**实现**：
- 独立 API：`POST /tools/polish-notice`
- 非流式（文本较短，不需要 SSE）
- System prompt 来自 `docs/二阶段项目需求.md` 中"公告润色助手"需求

**前端**：教师工具页面的一个卡片，文本输入 + 风格下拉 + 生成按钮 + 结果预览区。

### 2.2 成绩波动诊断书

**场景**：老师输入学生姓名/学号，查看历次考试成绩趋势分析。

**输入**：`stu_id`（下拉选择）或 `stu_name`

**实现**：
- 后端从数据库拉取该学生的 `stu_exam_record` 全部数据
- LLM 分析趋势（进步/退步/波动），生成点评
- System prompt 来自 `docs/二阶段项目需求.md` 中"成绩诊断书"需求

**前端**：学生选择器 + 成绩折线图（已有 ECharts）+ AI 文字分析。

### 2.3 期末评语生成器

**场景**：老师输入关键词（如"调皮、数学好、爱打架"），AI 生成委婉的评语。

**输入**：`keywords`（字符串）

**实现**：
- 独立 API：`POST /tools/generate-comment`
- System prompt 来自 `docs/二阶段项目需求.md`
- 温度 0.9（需要创意性）

**前端**：关键词输入框 + 生成按钮 + 评语预览区 + 复制按钮。

## 三、架构

```
api/tools_api.py                   ← 新路由 (prefix="/tools")
       │
       ├─ POST /polish-notice      ← 公告润色
       ├─ POST /diagnose-score     ← 成绩诊断
       └─ POST /generate-comment   ← 期末评语

services/tools_service.py          ← LLM 调用 + prompt 构建
```

所有工具都是**非流式**（请求-响应模式），因为输出较短且无需渐进渲染。

## 四、动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `api/tools_api.py` | 新建 | 3 个工具端点 |
| `services/tools_service.py` | 新建 | Prompt 构建 + LLM 调用 |
| `main.py` | 修改 | 注册 tools 路由 |
| `static/index.html` | 修改 | 新增"教师工具"Tab + 3 个工具卡片 |
| `static/js/modules/tools.js` | 新建 | 前端交互逻辑 |

## 五、约束

1. **复用 LLM 客户端** — 用 `services/llm_service.py` 的 `get_llm_client()`
2. **不改 DAO** — 诊断书调用现有 `exam_dao.exam_get()`
3. **不改 config.json**
4. **非流式** — 所有工具都是 POST → 同步返回结果

## 六、暂不处理

- 违纪话术教练（来自二阶段需求，非刚需）
- 班会策划师
- 模拟面试官
- 校规 RAG
- 工具历史记录（当前不记录到 conversation 表）

## 七、验证方法

1. 启动服务，登录 teacher 账号
2. 点击"教师工具"Tab
3. 公告润色：输入"明天大扫除，大家带抹布"→ 选择"正式风"→ 输出格式化通知
4. 成绩诊断：选择一个学生 → 查看折线图 + AI 评语
5. 期末评语：输入"数学好，上课爱说话"→ 生成三明治式评语
