# Plan: RAG 知识库前端界面

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────┐
│  static/index.html                                       │
│  导航 + 模板（Vue 3 + Tailwind + Element Plus）            │
│                                                          │
│  activeTab === 'ragKnowledge'                            │
│  ├─ 上传面板（文件选择 → 预览 → 入库设置 → 确认）          │
│  └─ 搜索面板（搜索栏 → 结果列表）                          │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│  static/js/modules/ragManager.js                          │
│  Vue 响应式状态 + 交互方法                                  │
│                                                          │
│  上传流：onFileSelected → doUpload → doConfirm            │
│  搜索流：doSearch                                         │
│  Mock 数据：MOCK_UPLOAD / MOCK_CONFIRM / MOCK_SEARCH      │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│  static/js/app.js — 主入口                                │
│  import → setup() → return                                │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│  后端 API                                                │
│  POST /rag/upload  POST /rag/confirm                     │
│  GET  /rag/models  POST /rag/search                      │
└──────────────────────────────────────────────────────────┘
```

## 2. 数据流

### 上传流

```
用户选择 .txt 文件
    │
    ▼
onFileSelected(file)
    │  selectedFile.value = file（仅前端存储，不触发 API）
    ▼
用户点击"上传预览"
    │
    ▼
doUpload()
    │  FormData(file) → POST /rag/upload
    │  成功 → uploadResult / previewChunks 更新
    │  失败 → ElMessage.error()
    ▼
预览区显示前 5 片内容（index + content）
用户调整模型/切片大小/重叠量
    │
    ▼
用户点击"确认入库"
    │
    ▼
doConfirm()
    │  {filename, chunk_size, chunk_overlap, model} → POST /rag/confirm
    │  成功 → confirmResult 更新，绿色成功提示
    │  失败 → ElMessage.error()
    ▼
入库完成
```

### 搜索流

```
用户输入查询文本 → 点击搜索 / 回车
    │
    ▼
doSearch()
    │  {query, top_k: 5} → POST /rag/search
    │  成功 → searchResults / searchTotal 更新
    │  失败 → ElMessage.error()
    ▼
结果列表渲染
┌─────────────────────────────────────┐
│ 匹配度: ████████░░ 85%              │
│ 来源:  test_novel.txt · 第 1/2 片   │
│ ─────────────────────────────────── │
│ 话说林黛玉自从来到荣国府...          │
└─────────────────────────────────────┘
```

### Mock → 真实切换策略

`ragManager.js` 内部维护 `useMock` 开关（默认 `true`），每个方法内部：

```
async function doUpload() {
    if (useMock) {
        await delay(800);
        return handleUploadResponse(MOCK_UPLOAD);
    }
    // 真实 axios 调用
}
```

联调时 `useMock = false` 即可切换为真实 API。

## 3. 组件设计

### 3.1 模块状态

```javascript
// 上传流程
selectedFile: File | null          — 用户选择的文件对象
uploadResult: Object | null        — /rag/upload 返回的 data
previewChunks: Array               — 预览切片 [{index, content}, ...]
confirmResult: Object | null       — /rag/confirm 返回的 data

// 入库设置
vectorModels: ['text-embedding-v3', 'text-embedding-v4']
selectedModel: 'text-embedding-v3'
chunkSize: 500
chunkOverlap: 100

// 搜索
searchQuery: ''
searchResults: Array               — [{source, content, score, chunk_id, metadata}, ...]
searchTotal: 0

// 通用
ragLoading: false                   — 全局 loading 状态
useMock: true                       — Mock/真实开关
```

### 3.2 方法定义

| 方法 | 触发时机 | API | 副作用 |
|------|----------|-----|--------|
| `onFileSelected(file)` | 用户选择文件 | 无（前端仅存储） | `selectedFile` 赋值 |
| `doUpload()` | 点击上传预览 | `POST /rag/upload` | 更新 `uploadResult`、`previewChunks` |
| `doConfirm()` | 点击确认入库 | `POST /rag/confirm` | 更新 `confirmResult` |
| `doSearch()` | 点击搜索/回车 | `POST /rag/search` | 更新 `searchResults`、`searchTotal` |
| `resetUpload()` | 上传完成后的"重新上传" | 无 | 重置所有上传相关状态 |

### 3.3 错误处理策略

| 场景 | 用户提示 |
|------|----------|
| 未选择文件点上传 | `ElMessage.warning('请先选择文件')` |
| 非 .txt 文件 | `ElMessage.warning('仅支持 .txt 文件')` |
| 文件 >10MB | `ElMessage.warning('文件大小超过 10MB 限制')` |
| API 返回 4xx/5xx | `ElMessage.error(err.response?.data?.detail || '操作失败，请稍后重试')` |
| 搜索前知识库为空 | 搜索区提示"知识库为空，请先上传文档"（不弹错误） |
| 搜索无结果 | 结果区显示"未找到相关内容" |

### 3.4 空状态与边界

| 状态 | 展示 |
|------|------|
| 初始（未选文件） | 拖放区域 + 点击选择按钮 |
| 已选文件未上传 | 显示文件名和字符数 + 上传按钮 |
| 上传后预览 | 切片列表 + 入库参数设置 |
| 入库成功 | 绿色成功卡片（含切片数/模型名）+ "继续上传"入口 |
| 搜索栏初始态 | 输入框 placeholder + 搜索按钮 |
| 搜索无结果 | "未找到相关内容"文案 |
| 搜索前库为空 | "知识库为空，请先上传文档"文案 |

## 4. 模板结构

### 4.1 导航项

插入在"文生图"和"教师工具"之间，所有角色可见：

```html
<a href="#"
    @click.prevent="activeTab = 'ragKnowledge'"
    :class="['flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 app-nav-item', sidebarCollapsed ? 'justify-center px-3' : '', activeTab === 'ragKnowledge' ? 'app-nav-item-active' : '']"
    :title="sidebarCollapsed ? '知识库' : ''">
    <i class="fas fa-book-open w-5"></i>
    <span v-show="!sidebarCollapsed">知识库</span>
</a>
```

### 4.2 Tab 内容区

```
v-if="activeTab === 'ragKnowledge'" 时渲染：

┌──────────────────────────────────────────────────────┐
│  📚 知识库                                            │
│  上传文档 → 智能切片 → 语义检索                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────── 上传文档 ──────────────────────────┐  │
│  │  拖放区域 / 点击选择文件                         │  │
│  │  (仅 .txt, ≤10MB)                              │  │
│  │                                [选择文件]       │  │
│  │                                                │  │
│  │  <selectedFile 时显示:>                          │  │
│  │  📄 test_novel.txt (296 字符)  [上传预览]        │  │
│  │                                                │  │
│  │  <previewChunks 时显示:>                        │  │
│  │  ── 切片预览（前 5 片） ──                      │  │
│  │  [0] 话说林黛玉自从来到荣国府...                │  │
│  │  [1] 贾母一见黛玉，便搂在怀里...                │  │
│  │                                                │  │
│  │  ── 入库设置 ──                                │  │
│  │  向量模型: [text-embedding-v3 ▼]               │  │
│  │  切片大小: [500]  重叠: [100]                  │  │
│  │                           [📥 确认入库]        │  │
│  │                                                │  │
│  │  <confirmResult 时显示:>                        │  │
│  │  ✅ 入库成功！共 2 片 (text-embedding-v3)       │  │
│  │                            [继续上传]           │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────── 知识检索 ──────────────────────────┐  │
│  │  [🔍 输入搜索内容...]         [搜索]           │  │
│  │                                                │  │
│  │  <searchTotal > 0 时显示:>                      │  │
│  │  共 N 条结果                                    │  │
│  │  ┌──────────────────────────────────────────┐  │  │
│  │  │ ████████░░ 85% · test_novel.txt · 第1/2片│  │  │
│  │  │ 话说林黛玉自从来到荣国府...              │  │  │
│  │  └──────────────────────────────────────────┘  │  │
│  │  ...                                           │  │
│  │                                                │  │
│  │  <searchTotal === 0 且已搜索 时显示:>           │  │
│  │  🔍 未找到相关内容                             │  │
│  │                                                │  │
│  │  <从未搜索过 时显示:>                           │  │
│  │  🔍 输入关键词搜索知识库内容                    │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## 5. Mock 数据

```javascript
// 上传预览
const MOCK_UPLOAD = {
    code: 200, message: "success",
    data: {
        filename: "test_novel.txt",
        total_chars: 296,
        total_chunks: 1,
        preview: [
            { index: 0, content: "话说林黛玉自从来到荣国府，步步留心，时时在意，不肯轻易多说一句话，多行一步路，怕被人耻笑了去。\n贾母一见黛玉，便搂在怀里痛哭，说：我这些儿女，所疼者独有你母亲，今日一旦先舍我而去，连面也不能一见，今见了你，我怎不伤心！" }
        ]
    }
};

// 确认入库
const MOCK_CONFIRM = {
    code: 200, message: "success",
    data: { filename: "test_novel.txt", total_chunks: 2, model: "text-embedding-v3", status: "ingested" }
};

// 搜索
const MOCK_SEARCH = {
    code: 200, message: "success",
    data: {
        results: [
            { chunk_id: "mock-001", source: "test_novel.txt", content: "话说林黛玉自从来到荣国府，步步留心，时时在意，不肯轻易多说一句话...", score: 0.85, metadata: { chunk_index: 0, total_chunks: 2 } },
            { chunk_id: "mock-002", source: "test_novel.txt", content: "宝玉笑道：我送妹妹一妙字，莫若颦颦二字极妙...", score: 0.72, metadata: { chunk_index: 1, total_chunks: 2 } }
        ],
        total: 2
    }
};

// 空搜索
const MOCK_SEARCH_EMPTY = {
    code: 200, message: "success",
    data: { results: [], total: 0 }
};
```

## 6. 文件清单

### 新建

| 文件 | 行数预估 | 职责 |
|------|----------|------|
| `static/js/modules/ragManager.js` | ~250 行 | 全模块逻辑（状态 + 方法 + mock） |

### 修改

| 文件 | 行数增量 | 改动 |
|------|----------|------|
| `static/index.html` | ~80 行 | 导航项 + 上传面板模板 + 搜索面板模板 |
| `static/js/app.js` | ~4 行 | 导入 + setup + return |

### 不动

`api/`、`services/`、`schemas/`、`core/`、`config.json`、`main.py`、已有模块文件

## 7. 原子任务清单

### P0 — 模块文件

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 1 | 创建 `ragManager.js` — 状态定义 | 所有响应式状态（selectedFile/uploadResult/previewChunks/confirmResult/vectorModels/selectedModel/chunkSize/chunkOverlap/searchQuery/searchResults/searchTotal/ragLoading/useMock） | 导入模块后所有状态可访问，默认值正确 |
| 2 | 实现 `onFileSelected()` + 文件校验 | 接受 File 对象，校验 .txt 后缀和 ≤10MB，赋值到 selectedFile | mock 一个 .txt 文件传入 → selectedFile 更新；传入 .md → 拒绝 |
| 3 | 实现 `doUpload()` — mock 版 | 使用 MOCK_UPLOAD 模拟上传预览，响应延迟 800ms | 调用后 previewChunks 填充为 mock 数据 |
| 4 | 实现 `doConfirm()` — mock 版 | 使用 MOCK_CONFIRM 模拟确认入库 | 调用后 confirmResult 填充 |
| 5 | 实现 `doSearch()` — mock 版 | 使用 MOCK_SEARCH / MOCK_SEARCH_EMPTY 模拟搜索 | 调用后 searchResults 非空 / 空 |
| 6 | 实现 `resetUpload()` | 重置 selectedFile / uploadResult / previewChunks / confirmResult | 调用后所有上传状态归零 |

### P1 — 模板

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 7 | index.html — 导航项 | 侧边栏新增"知识库"nav item（book-open 图标，所有角色可见） | 任意角色登录后侧边栏可看到"知识库" |
| 8 | index.html — 上传面板模板 | 文件选择区 + 预览区 + 入库设置区 + 确认按钮 + 成功提示，全部含 v-if 条件渲染 | 未选文件：显示拖放区；已选文件：显示文件名+上传按钮；预览后：显示切片列表+设置 |
| 9 | index.html — 搜索面板模板 | 搜索栏 + 结果列表 + 空状态 + 无结果提示 | 搜索前显示初始提示；搜索无结果显示空状态；有结果显示列表 |

### P2 — 集成

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 10 | app.js — 注册 ragManager 模块 | `import { createRagModule }` + `const rag = createRagModule()` + `...rag` | 模板中可访问 ragManager 的状态和方法 |
| 11 | 全局 loading 绑定 | `ragLoading` 绑定到所有操作按钮的 loading 状态 | 操作进行中按钮显示 spinner 且不可重复点击 |

### P3 — 验证

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 12 | Mock 模式完整走查 | 导航 → 选文件 → 上传预览 → 调参数 → 确认入库 → 搜索 → 看结果 | 见验证章节 |
| 13 | 真实模式切换 | `useMock = false`，登录后操作真实 API | 上传真实文件 → 入库 → 搜索 → 结果含真实 chunk_id 和 score |

## 8. 验证

### 8.1 Mock 模式冒烟测试（任务 12）

1. 启动前端（`python main.py` 或直接浏览器打开 `index.html`）
2. 任意角色登录
3. 侧边栏点击"知识库" → 切换到上传/搜索面板
4. **上传面板初始态**：拖放区域可见，选择文件按钮可用
5. **选择文件**：点选择 → 选一个 .txt → 显示文件名和字符数
6. **上传预览**：点"上传预览" → 按钮 loading → 800ms 后预览区显示 mock 切片列表
7. **确认入库**：调整模型/参数 → 点"确认入库" → loading → 显示绿色成功提示
8. **继续上传**：点"继续上传" → 状态重置
9. **搜索面板**：输入任意内容 → 点搜索 / 回车 → loading → 显示 2 条 mock 结果（含匹配度进度条、来源、内容摘要）
10. **非 .txt 文件**：尝试选择 .md 文件 → 提示"仅支持 .txt"
11. **大于 10MB 文件**：验证拦截

### 8.2 真实 API 联调（任务 13）

1. 启动服务（`python main.py`）
2. 设置 `useMock = false`
3. 登录后进入知识库页面
4. 上传一个真实的 .txt 文件 → 预览
5. 确认入库 → 检查后端日志含"第X片, 共Y片"
6. 搜索已导入的内容 → 结果含真实 chunk_id、source、score

### 8.3 回归验证

| 用例 | 预期 |
|------|------|
| 其他 Tab（仪表板/数据对话/黛玉等）不受影响 | 切换正常，数据加载正常 |
| 页面刷新后知识库状态重置 | 回到初始态（上传区和搜索区均为空） |
| 侧边栏折叠/展开 | 知识库 nav item 正常显示/隐藏文字 |
