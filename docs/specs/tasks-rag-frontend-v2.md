# RAG 知识库增强 V2 — 原子任务清单

> 基于 [todo_rag-frontend-v2.md](todo_rag-frontend-v2.md) 和 [plan-rag-frontend-v2.md](plan-rag-frontend-v2.md)

---

## P0 — 后端 Schema + 基础设施

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 1 | **rag_schemas.py — 新增 Schema** | 新增 `DocumentItem(id, filename, total_chunks, model, chunk_size, chunk_overlap, created_at)`、`DocumentListResponse(documents: list[DocumentItem], total: int)`、`StatsResponse(total_documents: int, total_chunks: int)` 三个 Pydantic model | `python -c "from schemas.rag_schemas import DocumentItem, DocumentListResponse, StatsResponse; print('OK')"` 不报错 |
| 2 | **rag_core.py — ChromaStore 新增 delete_by_filter + get_all** | ChromaStore 新增 `delete_by_filter(filter: dict) -> None` 和 `get_all() -> list[Chunk]` 两个方法 | `python -c "from services.rag_core import ChromaStore; print(hasattr(ChromaStore, 'delete_by_filter') and hasattr(ChromaStore, 'get_all'))"` 输出 True |

## P1 — 后端元数据管理 + 服务层

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 3 | **rag_service.py — DocumentMetadata 元数据管理** | 新增 `DocumentMetadata` 类，提供 `load()`、`save()`、`add_doc(doc_id, info)`、`remove_doc(doc_id)` 四个静态方法，操作 `./chroma_db/rag/documents.json` | `python -c "from services.rag_service import DocumentMetadata; DocumentMetadata.add_doc('test', {'filename':'a.txt'}); m=DocumentMetadata.load(); assert 'test' in m['documents']; DocumentMetadata.remove_doc('test'); print('OK')"` 元数据文件正确读写 |
| 4 | **rag_service.py — 服务层方法** | 在 `RAGEngine` 或 `IngestionPipeline` 中新增 `list_documents() -> DocumentListResponse`、`delete_document(doc_id: str)`、`get_stats() -> StatsResponse` 三个方法；confirm 入库后自动写入元数据 | `python -c "from services.rag_service import RAGEngine; print(hasattr(RAGEngine, 'list_documents') and hasattr(RAGEngine, 'delete_document') and hasattr(RAGEngine, 'get_stats'))"` 输出 True |

## P2 — 后端 API 端点

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 5 | **novel_rag_api.py — 新增 3 个端点** | `GET /rag/list`（返回文档列表）、`DELETE /rag/delete?doc_id=xxx`（删除文档）、`GET /rag/stats`（返回库统计），三个端点均需 JWT 认证 | 启动服务后 `curl -H "Authorization: Bearer $(curl -s -XPOST .../auth/token -d '...' \| jq -r '.access_token')" http://localhost:8080/rag/list` 返回 `{"code":200,...}` |

## P3 — 前端状态与方法

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 6 | **ragManager.js — 新增状态变量** | 新增 `ingestPhase`、`documents`、`docTotal`、`stats`、`statsLoading`、`deleteLoading` 共 6 个 `ref`，默认值分别为 `''`、`[]`、`0`、`null`、`false`、`false` | 浏览器控制台 `const m = createRagModule()` → 全部新状态存在且默认值正确 |
| 7 | **ragManager.js — 入库分阶段反馈** | 修改 `doConfirm()`：ragLoading=true 时通过 setTimeout 链依次设置 ingestPhase='chunking'→'embedding'→'indexing'；API 返回后清除定时器；成功后 ElMessage.success + 调用 fetchDocuments/fetchStats；失败 ElMessage.error | 点击确认入库 → 按钮文字依次变化；成功弹出成功提示；失败弹出错误提示且按钮恢复 |
| 8 | **ragManager.js — 文档列表 + 删除 + 统计方法** | 新增 `fetchDocuments()`（GET /rag/list → 赋值 documents/docTotal）、`fetchStats()`（GET /rag/stats → 赋值 stats）、`confirmDelete(doc)`（ElMessageBox.confirm → DELETE /rag/delete → 刷新列表）三个方法 | 调用 fetchDocuments → documents 填充为数组；调用 confirmDelete → 弹出确认框 → 确认后调用删除 API → 列表刷新 |

## P4 — 前端模板

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 9 | **index.html — 库概览统计** | 知识库页面顶部显示 "文档总数: N | 切片总数: N" 统计行，数据绑定 `stats`，`statsLoading` 时显示骨架屏 | 进入知识库页签 → 顶部显示统计数据 |
| 10 | **index.html — 文档表格** | 文档列表以表格形式渲染：列含文件名、切片数、向量模型、入库时间、操作（删除按钮）；空时显示 "知识库为空，请上传文档"；`deleteLoading` 时删除按钮禁用 | 有文档则显示表格；无文档则显示空状态引导；删除进行中按钮禁用 |
| 11 | **index.html — 增强确认入库按钮** | 按钮绑定 `ingestPhase`：ragLoading 时显示对应阶段文案（正在切片…/正在生成向量…/正在重建索引…）而非通用 spinner 文字 | 点击确认入库 → 按钮文字随阶段变化 |
| 12 | **index.html — 搜索面板空库提示** | 搜索面板在文档列表为空（`docTotal === 0`）时，搜索框下方显示 "知识库为空，请先上传文档"，且禁用搜索按钮 | 清空知识库 → 搜索面板显示空库提示；点搜索按钮无反应 |

## P5 — 样式

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 13 | **rag.css — 新增样式** | 文档表格样式、统计概览行样式、空状态引导样式、确认按钮阶段文字样式 | 所有新增组件视觉无误，与现有风格一致 |

## P6 — 验证

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 14 | **端到端全流程验证** | 完整走通: 上传 → 预览 → 分阶段入库 → 列表刷新 → 搜索 → 删除 → 空状态 | 见下方验证用例 |

### 验证用例（任务 14）

1. 启动服务 `python main.py`，登录后进入知识库页签
2. **文档列表自动加载**：页面顶部显示统计（文档数/切片数），下方表格列出所有已入库文档
3. **空知识库状态**：若为空，表格区显示「知识库为空，请上传文档」，搜索区显示「知识库为空，请先上传文档」，搜索按钮禁用
4. **选择文件 + 上传预览**：选一个 .txt → 上传 → 预览区显示切片
5. **分阶段入库**：点"确认入库"→ 按钮文字：正在切片… → 正在生成向量… → 正在重建索引… → 成功弹出 ElMessage.success + 内联绿色卡片
6. **入库失败恢复**：断网或制造后端错误 → ElMessage.error + 按钮恢复可点击（可重试）
7. **文档列表自动刷新**：入库成功后文档列表新增条目，统计数据更新
8. **搜索**：输入查询 → 搜索 → 显示结果（文档非空时）；空库时搜索按钮禁用且有提示
9. **删除文档**：点某文档的删除按钮 → ElMessageBox.confirm → 确认 → API 调用 → 列表刷新 + ElMessage.success
10. **删除失败**：制造后端错误 → ElMessage.error
11. **回归**：其他 Tab 不受影响；切换 Tab 再切回来状态保留（Vue 响应式）
