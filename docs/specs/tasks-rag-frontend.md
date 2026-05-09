# RAG 知识库前端界面 — 原子任务清单

## P0 — ragManager.js 模块实现

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 1 | 创建文件，定义全部响应式状态 | ragManager.js 存在，导出 `createRagModule()`，含 `selectedFile/uploadResult/previewChunks/confirmResult/vectorModels/selectedModel/chunkSize/chunkOverlap/searchQuery/searchResults/searchTotal/ragLoading/useMock` 共 13 个状态 | 在浏览器 console 执行 `const m = createRagModule()` → 所有状态可访问，类型默认值正确 |
| 2 | 实现 `onFileSelected()` + 文件校验 | 接受 File 对象，校验 .txt 后缀和 ≤10MB，赋值到 selectedFile | 选一个 .txt 文件 → selectedFile 更新；选 .md 文件 → 拒绝并弹提示 |
| 3 | 实现 `doUpload()`（mock 版） | 使用 MOCK_UPLOAD，模拟 800ms 延迟后填充 previewChunks | 调用后 previewChunks 为含 index/content 的数组 |
| 4 | 实现 `doConfirm()`（mock 版） | 使用 MOCK_CONFIRM，模拟 800ms 延迟后填充 confirmResult | 调用后 confirmResult.status === "ingested" |
| 5 | 实现 `doSearch()`（mock 版） | 根据 query 是否为空返回 MOCK_SEARCH 或 MOCK_SEARCH_EMPTY | 有 query → searchResults 长度 2；空 query → searchResults 为空数组 |
| 6 | 实现 `resetUpload()` | 重置 selectedFile/uploadResult/previewChunks/confirmResult 为初始值 | 调用后 4 个状态全部归零 |

## P1 — 模板与页面集成

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 7 | index.html — 添加"知识库"导航项 | 侧边栏新增 `<a>` nav item，含 book-open 图标，所有角色可见 | 任意角色登录 → 侧边栏看到"知识库"图标和文字；点击 → activeTab 切换 |
| 8 | index.html — 渲染上传面板 | 文件选择区 + previewChunks 列表 + 入库设置（模型下拉/切片大小/重叠量输入）+ 确认按钮 + confirmResult 成功提示 | 未选文件 → 拖放区可见；选文件后 → 文件名+上传按钮；预览后 → 切片列表+入库设置；入库后 → 绿色成功卡片 |
| 9 | index.html — 渲染搜索面板 | 搜索栏 + searchResults 结果列表（含匹配度/来源/切片序号/内容摘要）+ 空状态 + 无结果提示 | 搜索前 → 初始提示；搜索无结果 → "未找到相关内容"；有结果 → 列表渲染 |
| 10 | app.js — 注册 ragManager 模块 | `import { createRagModule }` + setup 中实例化 + return 中展开 | 模板中可访问 `ragLoading`、`doUpload`、`doSearch` 等状态和方法 |
| 11 | 全局 loading 绑定 | 上传预览/确认入库/搜索 三个操作按钮绑定 ragLoading，操作中禁用 | 点任意操作按钮 → 按钮显示 spinner 且不可重复点击；完成后恢复 |

## P2 — Mock 验证

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 12 | Mock 模式全流程走查 | 完整走通：导航 → 选文件 → 上传预览 → 调参数 → 确认入库 → 搜索 → 查看结果 | 见下方详细用例 |

### 验证用例（任务 12）

1. 任意角色登录，侧边栏点击"知识库"
2. 上传面板显示拖放区域和"选择文件"按钮
3. 点"选择文件"，选一个 .txt → 显示文件名和字符数
4. 点"上传预览" → 按钮 loading → 800ms 后显示 mock 切片列表（含序号和内容摘要）
5. 调整模型下拉 / 切片大小 / 重叠量 → 值正常变化
6. 点"确认入库" → loading → 显示绿色成功卡片（"入库成功！共 2 片 (text-embedding-v3)"）
7. 点"继续上传" → 上传面板恢复到初始态
8. 搜索面板输入"黛玉"→ 点搜索或回车 → loading → 显示 2 条结果
9. 每条结果含：匹配度进度条、来源文件名、切片序号（第X/Y片）、内容摘要
10. 选一个 .md 文件 → 提示"仅支持 .txt 文件"
11. 切换侧边栏折叠 → "知识库"文字隐藏/显示正常
12. 切换到其他 Tab 再切回来 → 上传/搜索面板状态保留
