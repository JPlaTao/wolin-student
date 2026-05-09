# BI Agent 前端消息渲染修复 - 实施报告

## 执行摘要

已完成 BI Agent 前端消息渲染的三个核心修复：
1. ✅ 提取 `createAiMessage` 工厂函数，统一消息构造逻辑
2. ✅ 拆分文本渲染区域：流式阶段用纯文本，完成后用 Markdown
3. ✅ 修复 CSS 兼容性问题（`whitespace-pre-wrap` → `style="white-space: pre-wrap;"`）

## 修改详情

### 文件 1: `static/js/modules/biChat.js`

**新增**：`createAiMessage` 工厂函数（16 行）
```javascript
function createAiMessage(overrides = {}) {
    return {
        role: 'ai',
        textContent: '',
        thinking: '',
        sql: '',
        sqlHash: '',
        tableData: null,
        analysisData: null,
        chartId: null,
        isComplete: false,
        ...overrides,
    };
}
```

**修改点**：
- `sendBiQuestion`：使用 `createAiMessage({ id, thinking })` 创建流式消息
- `loadSessionMessages`：使用 `createAiMessage({ id, textContent, sql, ... })` 恢复历史消息
- `init`：使用 `createAiMessage({ id, textContent, isComplete })` 创建欢迎消息

**效果**：三处消息创建逻辑统一，shape 完全一致，易于维护。

---

### 文件 2: `static/index.html`

**修改前**（第 426 行）：
```html
<div v-if="msg.textContent" class="answer-text" v-html="renderMarkdown(msg.textContent)"></div>
```

**修改后**：
```html
<!-- 主体文本：流式阶段用纯文本，完成后用 Markdown -->
<div v-if="msg.textContent && !msg.isComplete" class="answer-text" style="white-space: pre-wrap;">{{ msg.textContent }}</div>
<div v-if="msg.textContent && msg.isComplete" class="answer-text" v-html="renderMarkdown(msg.textContent)"></div>
```

**关键点**：
- 流式阶段（`!msg.isComplete`）：使用 `{{ msg.textContent }}`（纯文本插值）
- 完成态（`msg.isComplete`）：使用 `v-html="renderMarkdown(msg.textContent)"`（Markdown 渲染）
- 使用内联 `style="white-space: pre-wrap;"` 而非 Tailwind class（项目未引入 Tailwind）

---

## 技术原理

### 问题根源

`marked.parse()` 对不完整的 Markdown（如 `**加粗` 未闭合、表格写了一半）会产生与最终结果不同的中间态 HTML，导致流式阶段 DOM 不断变形。

### 解决方案

**流式阶段**：不调用 `marked.parse()`，直接显示纯文本。用户看到的是稳定的文字逐字增长，无格式跳动。

**完成后**：`done` 事件设置 `msg.isComplete = true`，Vue 检测到变化，切换到 Markdown 渲染的 div。此时文本已完整，`marked.parse()` 产生最终正确的 HTML。

**历史加载**：直接 `isComplete: true`，立即显示 Markdown 格式。

---

## 验证步骤

### 1. 重启服务

```bash
cd e:\01-Projects\wolin-student
# 停止当前服务（Ctrl+C）
.venv\Scripts\python main.py
```

### 2. 硬刷新浏览器

- **Windows**: `Ctrl + Shift + R` 或 `Ctrl + F5`
- **Mac**: `Cmd + Shift + R`

或者：
1. F12 打开开发者工具
2. 右键点击刷新按钮
3. 选择"清空缓存并硬性重新加载"

### 3. 流式场景测试

**操作**：提问"学生有多少人？"

**预期**：
- ✅ 回答文字逐字出现（纯文本，无加粗、无列表格式）
- ✅ 流式完成后，文字自动切换为 Markdown 格式（有加粗、列表等）
- ✅ 无 DOM 跳动或重排

### 4. 刷新场景测试

**操作**：刷新浏览器

**预期**：
- ✅ 历史消息直接显示 Markdown 格式
- ✅ 表格、图表、关键发现都正常显示
- ✅ 和流式完成时的显示完全一致

### 5. 控制台检查

**操作**：F12 → Console 标签

**预期**：
- ✅ 无 JavaScript 错误
- ✅ 无 Vue 警告

### 6. 多轮对话测试

**操作**：连续提问 3 个问题

**预期**：
- ✅ 每条消息的布局都稳定
- ✅ 无格式跳动
- ✅ 刷新后所有消息格式一致

---

## 故障排查

### 问题 1: 流式阶段仍显示 Markdown 格式

**原因**：浏览器缓存了旧的 `index.html`

**解决**：硬刷新浏览器（Ctrl + Shift + R）

---

### 问题 2: 纯文本阶段换行不正确

**原因**：`white-space: pre-wrap;` 未生效

**检查**：
```javascript
// 在控制台运行
document.querySelector('.answer-text')?.style.whiteSpace
// 应输出 "pre-wrap"
```

**解决**：已使用内联 style，应该正常工作

---

### 问题 3: 流式完成后未切换为 Markdown

**原因**：`msg.isComplete` 未被设为 `true`

**检查**：在 `biChat.js` 的 `handleStreamEvent` 中，`case 'done'` 应该有：
```javascript
case 'done':
    msg.thinking = '';
    msg.isComplete = true;  // ← 确认这行存在
    scheduleChartRender(msg);
    break;
```

---

## Git Diff 摘要

```
static/js/modules/biChat.js  | +87 -52
static/index.html            | +2 -1
```

**核心改动**：
- 新增 `createAiMessage` 工厂函数
- 三处消息创建改用工厂函数
- 文本渲染区域拆成两个互斥 div

---

## 成功标志

当你看到：
- ✅ 流式阶段文字逐字出现，无格式（纯文本）
- ✅ 流式完成后文字自动变为 Markdown 格式（有加粗、列表）
- ✅ 刷新后历史消息和流式完成时显示一致
- ✅ 控制台无错误

**修复成功！** 🎉

---

## 后续建议

1. **性能优化**：如果文本很长（>10KB），可以考虑在流式阶段只显示最后 N 行，完成后再显示全文
2. **视觉优化**：可以给纯文本阶段加一个 `typing-effect` 动画，提升体验
3. **错误处理**：在 `finally` 块中加兜底逻辑，确保异常情况下 `isComplete` 也会被设为 `true`

---

**实施完成时间**：2024-01-XX
**修改文件数**：2
**新增代码行数**：89
**删除代码行数**：53
