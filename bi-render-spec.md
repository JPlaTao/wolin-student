# Feature: BI Agent 前端消息渲染与布局

## Problem Statement

BI Agent 的 AI 消息渲染存在两个已确认的缺陷：

1. **流式 Markdown 渲染不一致**：流式阶段使用 `marked.parse()` 对不完整的 Markdown 文本进行解析（如半个表格、未闭合的代码块），产生的中间态 HTML 结构与流式完成后的最终态不同。用户看到的是一段不断变形的 DOM，体验差。

2. **历史消息数据丢失**：刷新页面后从 `/bi/sessions/{id}` 加载的历史消息，`tableData`、`analysisData`、`chartId` 原先全部硬编码为 `null`（此问题已在本轮修复），导致刷新前后内容不一致。但修复后又暴露了新问题——流式阶段和历史加载阶段使用不同的数据源构建相同的 UI 块，逻辑散落在两处，难以维护。

### 根本原因

当前 AI 消息是一个**扁平对象**，所有字段（`textContent`、`thinking`、`sql`、`tableData`、`analysisData`、`chartId`、`isComplete`）平铺在同一层。模板侧通过一系列 `v-if` 条件判断渲染哪些块。这导致：

- 流式写入和历史恢复必须各自构造相同 shape 的对象，逻辑重复
- 模板承担了过多的条件分支，难以理解渲染顺序
- `v-html="renderMarkdown(msg.textContent)"` 在流式过程中对不完整 Markdown 反复调用 `marked.parse()`，产生不稳定的 HTML 碎片

### 当前数据流

```
后端 SSE 事件序列（按实际到达顺序）:

thinking  → "正在生成 SQL 查询..."
sql       → { sql, sql_hash }
thinking  → "正在执行查询..."
data      → { success, columns, rows, row_count, ... }
thinking  → "正在分析数据..."
analysis  → { key_findings, chart_suggestion, statistics }
chunk     → "根据查询结果..."    ← 多次，逐字追加到 textContent
chunk     → "，五班的平均分..."
...
done      → ""
```

注意：**文本回答（chunk）在 data 和 analysis 之后才到达**。但当前模板把文本放在最上面（`v-if="msg.textContent"`），数据和分析在下面折叠。这意味着在流式阶段，文本区域一开始是空的，数据先出现，然后文本才逐字填入——和最终的视觉层级（文本在上）产生跳动。

### 当前模板结构（index.html 中 AI 消息块）

```
div.space-y-1
├── [thinking]    v-if="msg.thinking"        ← 加载指示器
├── [text]        v-if="msg.textContent"     ← Markdown 渲染 (v-html)
├── [findings]    v-if="analysisData?.key_findings"  ← 关键发现列表
└── <details>     v-if="msg.sql || msg.tableData"    ← 折叠区
    ├── [sql]
    ├── [table / single-value / empty]
    ├── [pagination]
    ├── [statistics]
    ├── [sql-error]
    └── [chart]
```

## Success Criteria

- 流式阶段和刷新加载后，同一条消息的 **布局结构、块顺序、可见性** 完全一致
- 流式期间，不完整 Markdown 不会产生可见的格式跳动（如闪现半截 `<table>` 标签）
- 历史消息加载后，表格、图表、关键发现与首次流式接收时显示内容一致
- 所有修改仅涉及前端文件（`biChat.js`、`index.html`、`app.js`），不改后端 API

## User Stories

1. 作为用户，我提问后看到的 AI 回答，从流式输出到最终呈现，布局不应发生跳动或重排
2. 作为用户，我刷新页面后，之前的对话内容（文本、表格、图表、关键发现）应与流式完成时一模一样
3. 作为用户，在 AI 回答尚未完成时，我应能看到清晰的进度指示（如"正在生成 SQL..."），而不是空白

## Acceptance Criteria

- [ ] AI 消息的渲染块顺序在流式阶段和历史加载阶段完全一致
- [ ] 流式期间，Markdown 文本使用纯文本或安全的增量渲染方式展示；流式完成后再一次性调用 `marked.parse()` 渲染最终格式
- [ ] `loadSessionMessages` 从 `result_summary` 恢复 `tableData`、`analysisData`、`chartId`（已完成）
- [ ] 流式完成的消息和历史加载的消息使用同一个数据 shape，不存在两套构造逻辑
- [ ] 图表在历史加载后能正确渲染（已完成）
- [ ] 无 JavaScript 控制台错误
- [ ] 不引入新的 npm 依赖或 CDN 资源

## Non-Goals

- 不改后端 SSE 事件格式或 API 接口
- 不重写会话管理（session CRUD）逻辑
- 不涉及 CSS 样式调整（布局结构变更除外）
- 不处理网络中断重连、SSE 断线续传
- 不做消息编辑、删除、重新生成等交互

## Constraints

- 技术栈不变：Vue 3 CDN（Options 风格使用 `setup()` return）+ 原生 JS 模块，不引入构建工具
- `marked` 通过 CDN `<script>` 标签全局加载（`window.marked`），不改加载方式
- `renderMarkdown` 定义在 `app.js` 中作为模板方法，不迁移到模块内部
- ECharts 通过 CDN 全局加载（`window.echarts`）
- `biChat.js` 是一个 ES module，通过工厂函数 `createBiChatModule` 导出响应式状态和方法
- `index.html` 是单文件 SPA，所有模板都在其中，不能拆分为 `.vue` 组件

## Technical Context

### 消息对象 Shape（当前）

```javascript
// AI 消息
{
  id: Number,
  role: 'ai',
  textContent: String,      // Markdown 文本（流式追加）
  thinking: String,          // 当前思考阶段提示
  sql: String,               // 生成的 SQL
  sqlHash: String,           // SQL 哈希（翻页用）
  tableData: Object | null,  // { success, columns, rows, row_count, page, ... }
  analysisData: Object | null, // { key_findings, chart_suggestion, statistics }
  chartId: String | null,    // ECharts 容器 DOM id
  isComplete: Boolean,       // 流式是否结束
}
```

### SSE 事件类型与到达顺序

| 顺序 | 事件类型 | 数据 | 前端处理 |
|------|---------|------|---------|
| 1 | `thinking` | 提示文本 | `msg.thinking = data` |
| 2 | `sql` | `{ sql, sql_hash }` | 设置 `msg.sql`, `msg.sqlHash` |
| 3 | `thinking` | 提示文本 | `msg.thinking = data` |
| 4 | `data` | 查询结果对象 | `msg.tableData = data` |
| 5 | `thinking` | 提示文本 | `msg.thinking = data` |
| 6 | `analysis` | 分析结果对象 | `msg.analysisData = data` |
| 7+ | `chunk` | 文本片段 | `msg.textContent += data` |
| N | `done` | 空 | `msg.isComplete = true` |

### Markdown 渲染

```javascript
// app.js 中定义
const renderMarkdown = (text) => {
    if (typeof marked !== 'undefined') return marked.parse(text);
    return text;
};
```

`marked.parse()` 是一个同步的全量解析器。每次调用都对整个文本重新解析。在流式追加场景下，这意味着每收到一个 `chunk` 就重新解析一次全文。对于不完整的 Markdown（如 `**加粗` 没闭合、表格语法写了一半），`marked` 会产生不同于最终结果的中间态 HTML。
