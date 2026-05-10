# Plan: RAG 知识库增强 V2 — 入库反馈 + 文档管理

> 基于 [todo_rag-frontend-v2.md](todo_rag-frontend-v2.md) 的产品需求规格
> 本文档定位：连接产品需求与代码实现之间的桥梁，描述架构设计、组件分解、数据流和关键技术决策

---

## 1. 当前架构概览 (As-Is)

### 1.1 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (static/index.html + js/modules/ragManager.js)        │
│  Vue 3 (CDN) + Element Plus + Axios                         │
│  状态: Vue ref (ragLoading, uploadResult, confirmResult 等) │
├─────────────────────────────────────────────────────────────┤
│  后端 API (api/novel_rag_api.py)                             │
│  FastAPI Router prefix=/rag, JWT 认证                       │
│  4个端点: upload / confirm / models / search                 │
├─────────────────────────────────────────────────────────────┤
│  服务层 (services/rag_service.py)                            │
│  DocumentProcessor / IngestionPipeline / RAGEngine          │
├─────────────────────────────────────────────────────────────┤
│  基础设施 (services/rag_core.py)                             │
│  ChromaStore / BM25Index / Reranker / HybridRetriever       │
├─────────────────────────────────────────────────────────────┤
│  存储层                                                      │
│  chroma_db/rag/ (向量库 + BM25 pickle)                      │
│  data/uploads/ (原始上传文件)                                │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 当前局限

| 问题 | 表现 | 原因 |
|------|------|------|
| 入库无阶段反馈 | 全程只显示 "入库中..." spinner | 后端同步 API，前端无阶段模拟提示 |
| 无入库成功弹窗 | 只有内联绿色卡片 | 缺乏 ElMessage.success 调用 |
| 无法查看库内文档 | 无文档列表渲染 | 缺少 list API + 前端列表组件 |
| 无法删除文档 | 无删除入口 | 缺少 delete API + 前端删除流程 |
| 无空状态引导 | 列表区域空白 | 无空状态组件 |
| 搜索无文档提示 | 有/无文档时搜索区域一致 | 缺少状态区分 |

---

## 2. 目标架构 (To-Be)

### 2.1 新增/修改内容

```
前端新增:
  - 入库分阶段模拟反馈 (setTimeout)
  - ElMessage.success/error 弹窗
  - 文档列表 (表格: 文件名/切片数/模型/时间/操作)
  - 删除文档 (二次确认 + API 调用)
  - 空状态引导
  - 搜索面板状态感知

后端新增:
  - GET /rag/list   — 文档列表
  - DELETE /rag/delete — 删除文档
  - GET /rag/stats  — 库概览 (文档数/切片数)
  - 元数据持久化 (JSON 元数据文件)
```

### 2.2 新增组件树

```
ragKnowledge (v-if tab)
├── 库概览统计 (文档总数 / 切片总数)           ← 新增
├── 上传面板 (左列)
│   ├── 文件选择区
│   ├── 预览区
│   ├── 入库设置
│   ├── 确认入库按钮 (分阶段提示)              ← 增强
│   └── 入库成功内联卡片 + ElMessage.success   ← 增强
├── 文档管理面板 (左列, 上传面板下方)          ← 新增
│   ├── 文档表格 (文件名/切片数/模型/入库时间)
│   │   └── 每行: 删除按钮
│   ├── 空状态引导 ("知识库为空，请上传文档")
│   └── 删除确认弹窗 (ElMessageBox.confirm)
└── 搜索结果面板 (右列)
    ├── 库为空提示                              ← 新增状态
    ├── 搜索输入框 + 按钮
    ├── 初始提示
    └── 结果列表
```

---

## 3. 新增 API 详细设计

### 3.1 GET /rag/list — 文档列表

**用途**: 返回知识库中所有已入库文档的元数据

**请求**:
```
GET /rag/list
Authorization: Bearer <token>
```

**响应** (200):
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "documents": [
      {
        "id": "doc_001",
        "filename": "教学设计-2025春.txt",
        "total_chunks": 24,
        "model": "text-embedding-v3",
        "chunk_size": 500,
        "chunk_overlap": 100,
        "created_at": "2026-05-10T14:30:00"
      }
    ],
    "total": 1
  }
}
```

### 3.2 DELETE /rag/delete — 删除文档

**用途**: 删除指定文档及其所有切片（向量 + BM25）

**请求**:
```
DELETE /rag/delete?doc_id=doc_001
Authorization: Bearer <token>
```

**响应** (200):
```json
{
  "code": 200,
  "message": "文档 doc_001 已删除"
}
```

### 3.3 GET /rag/stats — 库概览

**用途**: 返回知识库统计信息（文档总数、切片总数）

**请求**:
```
GET /rag/stats
Authorization: Bearer <token>
```

**响应** (200):
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total_documents": 5,
    "total_chunks": 128
  }
}
```

### 3.4 元数据持久化方案

**决策: JSON 元数据文件** (而非新增 SQL model)

- **原因**: RAG 系统目前完全基于文件存储（Chroma + BM25 pickle），新增 SQL model 会引入混合持久化层的复杂性；现有 infra 层无 DB session 依赖
- **方案**: 在 `./chroma_db/rag/` 下维护 `documents.json` 元数据文件
- **内容**: 文档 ID → `{filename, total_chunks, model, chunk_size, chunk_overlap, created_at}` 映射
- **操作**: 入库成功时追加条目；删除时移除条目并同步清理 Chroma + BM25
- **并发**: 写操作通过 `threading.Lock` 加锁

---

## 4. 入库分阶段反馈机制

### 4.1 设计原理

后端 API 保持同步（非 SSE），前端用 `setTimeout` 链模拟阶段切换：

```
用户点击确认入库
  → ragLoading = true
  → 按钮文字: "正在切片…"          (即时)
  → 800ms 后: "正在生成向量…"      (setTimeout 1)
  → 2500ms 后: "正在重建索引…"     (setTimeout 2)
  → API 返回
    ├── 成功: ragLoading = false, ElMessage.success, 内联卡片, 刷新文档列表
    └── 失败: ragLoading = false, ElMessage.error, 按钮恢复可点击
```

### 4.2 状态变量

```javascript
const ingestPhase = ref('')  // '' | 'chunking' | 'embedding' | 'indexing'
```

### 4.3 模板绑定

```html
<el-button :loading="ragLoading" :disabled="ragLoading" @click="doConfirm">
  <template v-if="ragLoading">
    <span v-if="ingestPhase === 'chunking'">正在切片…</span>
    <span v-else-if="ingestPhase === 'embedding'">正在生成向量…</span>
    <span v-else-if="ingestPhase === 'indexing'">正在重建索引…</span>
    <span v-else>入库中…</span>
  </template>
  <template v-else>确认入库</template>
</el-button>
```

---

## 5. 前端状态管理

### 5.1 状态变量全表

| ref | 类型 | 用途 | 新增/已有 |
|-----|------|------|-----------|
| `selectedFile` | `File\|null` | 用户选择的文件 | 已有 |
| `uploadResult` | `Object\|null` | 上传响应 | 已有 |
| `previewChunks` | `Array` | 预览切片列表 | 已有 |
| `confirmResult` | `Object\|null` | 入库响应 | 已有 |
| `vectorModels` | `Array` | 可选向量模型 | 已有 |
| `selectedModel` | `String` | 选中模型 | 已有 |
| `chunkSize` | `Number` | 切片大小 | 已有 |
| `chunkOverlap` | `Number` | 切片重叠 | 已有 |
| `searchQuery` | `String` | 搜索关键词 | 已有 |
| `searchResults` | `Array` | 搜索结果 | 已有 |
| `searchTotal` | `Number` | 搜索结果总数 | 已有 |
| `hasSearched` | `Boolean` | 是否已搜索 | 已有 |
| `ragLoading` | `Boolean` | 全局加载状态 | 已有 |
| `ingestPhase` | `String` | 入库阶段标识 | **新增** |
| `documents` | `Array` | 文档列表 | **新增** |
| `docTotal` | `Number` | 文档总数 | **新增** |
| `statsLoading` | `Boolean` | 统计加载态 | **新增** |
| `stats` | `Object` | 库统计概览 | **新增** |
| `deleteLoading` | `Boolean` | 删除操作加载态 | **新增** |

### 5.2 数据流图

```
页面加载 (进入知识库页签)
  └→ fetchDocuments() → GET /rag/list → documents[], docTotal
  └→ fetchStats()     → GET /rag/stats → stats {total_documents, total_chunks}

上传流程:
  doUpload() → POST /rag/upload (FormData) → uploadResult + previewChunks

入库流程:
  doConfirm() → ingestPhase='chunking' → setTimeout → 'embedding' → setTimeout → 'indexing'
              → POST /rag/confirm → success: ElMessage + fetchDocuments() + fetchStats()
                                  → fail: ElMessage.error

删除流程:
  confirmDelete(doc) → ElMessageBox.confirm → DELETE /rag/delete?doc_id=...
    → success: fetchDocuments() + fetchStats() + ElMessage.success
    → fail: ElMessage.error

搜索流程:
  doSearch() → POST /rag/search → searchResults + searchTotal
```

---

## 6. 关键文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `schemas/rag_schemas.py` | **修改** | 新增 `DocumentItem` / `DocumentListResponse` / `StatsResponse` schema |
| `services/rag_core.py` | **修改** | ChromaStore 新增 `delete_by_filter()`、`get_all()` 方法 |
| `services/rag_service.py` | **修改** | 新增 `DocumentMetadata` 类 + `list_documents()` / `delete_document()` / `get_stats()` |
| `api/novel_rag_api.py` | **修改** | 新增 list / delete / stats 三个端点 |
| `static/js/modules/ragManager.js` | **修改** | 新增状态 + 方法 + API 调用 + 分阶段反馈 |
| `static/index.html` | **修改** | 新增文档列表/空状态/概览模板 + 增强确认按钮 + 搜索空库提示 |
| `static/css/rag.css` | **修改** | 新增文档表格/统计/空状态样式 |

---

## 7. 后端关键实现细节

### 7.1 ChromaStore 新增方法

```python
class ChromaStore(VectorStore):
    def delete_by_filter(self, filter: dict) -> None:
        """根据 metadata filter 删除向量条目"""
        # Chroma 支持 collection.delete(where=filter)
        # 用于删除某文档的所有切片: delete_by_filter({"source": "doc_001"})

    def get_all(self) -> list[Chunk]:
        """获取当前 collection 中所有条目（用于重建 BM25）"""
```

### 7.2 元数据管理

```python
METADATA_PATH = "./chroma_db/rag/documents.json"

class DocumentMetadata:
    @staticmethod
    def load() -> dict: ...
    @staticmethod
    def save(metadata: dict): ...
    @staticmethod
    def add_doc(doc_id: str, info: dict): ...
    @staticmethod
    def remove_doc(doc_id: str): ...
```

每个 chunk 的 Chroma metadata 中包含 `{"source": doc_id, "chunk_index": i}` 以便按文档删除和关联。

### 7.3 DELETE 完整流程

```
DELETE /rag/delete?doc_id=doc_001
  1. ChromaStore.delete_by_filter({"source": "doc_001"})
  2. 从 Chroma 读取剩余所有条目
  3. BM25Index.build(remaining) + BM25Index.save()
  4. DocumentMetadata.remove_doc("doc_001")
  5. 重置 RAGEngine 单例 (下次搜索重新加载)
```

---

## 8. 验证方案

| 验收项 | 验证方式 |
|--------|---------|
| 入库分阶段反馈 | 点击确认入库，观察按钮文字按 "切片→向量→索引" 变化 |
| 入库成功弹窗 | 确认入库成功后 ElMessage.success 弹出 |
| 入库失败弹窗 | 断网或制造错误，ElMessage.error 显示具体原因 |
| 文档列表自动加载 | 进入知识库页签，文档列表自动渲染 |
| 文档删除 | 点击删除→确认→列表刷新+成功弹窗 |
| 删除失败 | 制造后端错误，观察错误弹窗 |
| 空状态 | 清空知识库，观察 "知识库为空" 引导 |
| 搜索空库提示 | 在空知识库搜索，观察提示信息 |

**启动命令**:
```bash
.venv/Scripts/python main.py
# 访问 http://localhost:8080/static/index.html 登录后进入知识库
```
