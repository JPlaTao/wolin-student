# 数据对话 UI 重构 — 文本优先 + 数据折叠

> 状态: 待实现 | 优先级: P1 | 依赖: working_ai-chat-v2-architecture

---

## 一、现状问题

当前 `biChat.js` 的 `updateStreamingMessage()` 将所有内容拼成一个 HTML 字符串，固定顺序：

```
thinking → SQL → 表格 → 分析 → chunk 文本
```

前端通过 `v-html="msg.content"` 一次渲染。导致：

| 问题 | 原因 |
|------|------|
| 自然语言回答在最底部，SQL/表格反而在上面 | 拼装顺序固定，chunk 文本最后追加 |
| 表格渲染混乱 | `formatDataTable` 手写 HTML 表格，与 `marked` 渲染的 markdown 表格样式不统一 |
| 无视觉分层 | 所有内容混在一个 `v-html` 中 |

---

## 二、目标

**文本优先 + 数据折叠**：用户看到的是一条消息，但内容有清晰的分层结构。

## 三、消息数据结构

不再用 `msg.content` 拼 HTML 字符串。每个 AI 消息有独立的响应式字段，Vue 模板逐块渲染：

```javascript
msg = {
    id: 123,
    role: 'ai',

    // 主体文本 — LLM 的自然语言回复（chunk 累积），Markdown 渲染，始终可见
    textContent: '',

    // 思考状态 — 流式过程中显示的提示文字
    thinking: '',

    // === 查询详情（折叠区） ===

    sql: '',                // 生成的 SQL
    sqlHash: '',            // SQL 的 MD5，翻页用

    tableData: null,        // execute_sql 返回的 { columns, rows, row_count, page, total_pages, has_more, statistics, sql_hash }

    analysisData: null,     // analyze_data 返回的 AnalysisOutput { summary, key_findings, chart_suggestion, statistics }

    chartId: null,          // ECharts 容器 DOM id

    isComplete: false,      // 流式是否完成
}
```

## 四、视觉布局

```
┌──────────────────────────────────────┐
│ 🤖 AI                                │
│                                      │
│ [textContent — Markdown 渲染]         │  ← 始终可见，主体回答
│ 根据查询结果，共有 120 名学生...      │
│                                      │
│ • 关键发现 1                          │  ← key_findings 列表（始终可见）
│ • 关键发现 2                          │
│                                      │
│ ▶ 查询详情                           │  ← <details> 默认折叠
│   ┌─ SQL ─────────────────────────┐ │
│   │ SELECT COUNT(*) FROM ...      │ │
│   └───────────────────────────────┘ │
│   ┌─ 数据表格 ─────────────────────┐ │
│   │ | 班级 | 人数 | ...           │ │
│   │ 共 50 条，第 1/3 页 [下一页]  │ │
│   └───────────────────────────────┘ │
│   ┌─ 图表 ────────────────────────┐ │
│   │ [ECharts 柱状图]              │ │
│   └───────────────────────────────┘ │
└──────────────────────────────────────┘
```

## 五、SSE 事件 → 消息字段映射

不再调用 `updateStreamingMessage()` 重建 HTML，而是直接修改 msg 对象的响应式字段：

| SSE Event | 操作 |
|-----------|------|
| `thinking` | `msg.thinking = event.data` |
| `sql` | `msg.sql = event.data.sql`, `msg.sqlHash = event.data.sql_hash`, `msg.thinking = ''` |
| `data` | `msg.tableData = event.data`, `msg.thinking = ''` |
| `analysis` | `msg.analysisData = event.data`, `msg.thinking = ''` |
| `chunk` | `msg.textContent += event.data` |
| `done` | `msg.thinking = ''`, `msg.isComplete = true`, 渲染 ECharts 图表到 `msg.chartId` |
| `error` | 仅 console.error，不展示 |

## 六、模板改动（index.html）

当前一个 `v-html="msg.content"` 拆为结构化渲染：

```html
<div v-if="msg.role === 'ai'" class="space-y-1">
    <!-- 思考中 -->
    <div v-if="msg.thinking" class="text-blue-400 text-sm">
        <i class="fas fa-spinner fa-spin mr-1"></i>{{ msg.thinking }}
    </div>

    <!-- 主体文本（Markdown） -->
    <div v-if="msg.textContent" class="answer-text" v-html="renderMarkdown(msg.textContent)"></div>

    <!-- 关键发现 -->
    <ul v-if="msg.analysisData?.key_findings?.length"
        class="ml-4 list-disc text-sm text-slate-300 space-y-0.5">
        <li v-for="f in msg.analysisData.key_findings">{{ f }}</li>
    </ul>

    <!-- 查询详情（折叠） -->
    <details v-if="msg.sql || msg.tableData" class="mt-3">
        <summary class="cursor-pointer text-slate-500 text-xs hover:text-slate-300">
            <i class="fas fa-database mr-1"></i>查询详情
        </summary>
        <div v-if="msg.sql" class="mt-2">...</div>
        <div v-if="msg.tableData">表格 + 分页 + 统计</div>
        <div v-if="msg.chartId" :id="msg.chartId" class="h-64 mt-3 rounded-lg bg-slate-900/50"></div>
    </details>
</div>
```

## 七、表格渲染

不再手写 HTML 表格。利用 `marked` 库渲染 markdown 格式的表格：

```javascript
const buildMarkdownTable = (data) => {
    if (!data?.rows?.length) return '';
    const cols = data.columns;
    let md = '| ' + cols.join(' | ') + ' |\n';
    md += '| ' + cols.map(() => '---').join(' | ') + ' |\n';
    data.rows.forEach(row => {
        md += '| ' + cols.map(c => row[c] ?? '-').join(' | ') + ' |\n';
    });
    return md;
};
```

表格、分页控件、统计摘要通过 Vue 模板组合，不混入 markdown。

## 八、改动范围

| 文件 | 改动 |
|------|------|
| `static/js/modules/biChat.js` | 重写：移除 `updateStreamingMessage()` 和 `formatDataTable()`；SSE 事件处理直接改 msg 字段；新增 `buildMarkdownTable()` |
| `static/index.html` | "数据对话" Tab 的 AI 消息模板从单 `v-html` 改为结构化渲染 |

## 九、不变

- `sendBiQuestion()` 外层流式循环不变
- `buildEChartsOption()` / `renderChart()` 不变
- `goToPage()` 翻页逻辑不变（改为更新 `msg.tableData.rows` 和 `msg.tableData.page`）
- 后端无改动
