# RAG 知识库 — 完整规格说明书

> **本文件是 RAG 知识库的唯一真实来源**。代码是本规约的衍生物。如有不一致，以本文件为准。

---

## 1. 概述

RAG 知识库模块提供"上传文档 → 切片 → 向量化 → 混合检索 → 文档管理"的全链路能力。

### 1.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     前端 (static/)                                       │
│  index.html (Vue 3 + Element Plus 模板)                                  │
│  js/modules/ragManager.js (响应式状态 + 方法)                             │
│  js/app.js (注册 rag 模块)                                               │
└─────────────────────────┬────────────────────────────────────────────────┘
                          │ HTTP (JWT Auth)
┌─────────────────────────▼────────────────────────────────────────────────┐
│                  API 层 (api/novel_rag_api.py)                           │
│                                                                          │
│  POST /rag/upload     POST /rag/confirm     GET  /rag/models            │
│  POST /rag/search     GET  /rag/documents   DELETE /rag/documents/{fn}  │
│  GET  /rag/stats                                                         │
└────────┬──────────────────────────┬──────────────────────────────────────┘
         │                          │
┌────────▼──────────────────────────▼──────────────────────────────────────┐
│             业务层 (services/rag_service.py)                             │
│                                                                          │
│  DocumentProcessor           IngestionPipeline           RAGEngine       │
│  ├─ parse_txt()              ├─ preview()               ├─ search()      │
│  └─ chunk_text()             └─ ingest()                ├─ delete_doc()  │
│                                                         └─ get_stats()   │
└────────┬──────────────────────────┬──────────────────────────────────────┘
         │                          │
┌────────▼──────────────────────────▼──────────────────────────────────────┐
│          基础设施层 (services/rag_core.py)                                │
│                                                                          │
│  VectorStore (ABC)     ChromaStore       BM25Index       Reranker        │
│  ├─ add()              ├─ (实现所有       ├─ build()      └─ rerank()     │
│  ├─ search()           │   抽象方法)      ├─ save()/load()                │
│  ├─ count()            ├─ list_docs()    └─ search()    HybridRetriever  │
│  ├─ clear()            ├─ delete_by()                  └─ search()       │
│  ├─ list_documents()   └─ get_all()                    BM25∪Vec→Rerank   │
│  └─ delete_by_source()                                                     │
└────────┬──────────────────────────┬──────────────────────────────────────┘
         │                          │
┌────────▼──────────┐  ┌───────────▼──────────────────────────────────────┐
│ ./chroma_db/rag/  │  │ ./chroma_db/rag/bm25_index.pkl                   │
│  Chroma SQLite    │  │  BM25Okapi 序列化索引                             │
└───────────────────┘  └──────────────────────────────────────────────────┘
```

### 1.2 数据流

**上传→入库→检索 全流程：**

```
用户选择 .txt 文件
    → onFileSelected() 前端校验（后缀 .txt, ≤10MB）
    → doUpload() → POST /rag/upload → 后端保存文件 + 切片预览（前 5 片）
    → 用户调整参数（模型/切片大小/重叠量）
    → doConfirm() → POST /rag/confirm
        → 后端重新切片 → 逐片生成 Embedding → 写入 Chroma → 重建 BM25
    → 入库完成，前端刷新文档列表
    → doSearch() → POST /rag/search
        → 后端 BM25∪Vector→去重→Rerank → 返回 TopK
```

**文档管理流程：**

```
进入知识库页签
    → fetchDocuments() → GET /rag/documents → 渲染文档表格
    → fetchStats() → GET /rag/stats → 渲染概览统计
用户点击删除
    → confirmDelete() → ElMessageBox.confirm → 确认
    → DELETE /rag/documents/{filename}
        → 后端按 source 删除 Chroma 切片 → 重建 BM25 → 返回删除数量
    → 前端刷新文档列表 + 统计
```

---

## 2. 后端基础设施层

基础设施层的设计原则：**所有向量库操作通过抽象接口**，业务代码不直接依赖 Chroma SDK 类型。

### 2.1 VectorStore（抽象基类）

位置：`services/rag_core.py`

```python
from abc import ABC, abstractmethod

class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        """存入向量，返回 chunk_id 列表"""

    @abstractmethod
    def search(self, query_embedding: list[float], k: int) -> list[tuple[str, float]]:
        """余弦相似度检索，返回 [(chunk_id, score), ...]"""

    @abstractmethod
    def count(self) -> int:
        """当前集合中的切片总数"""

    @abstractmethod
    def clear(self) -> None:
        """清空整个集合（删除 collection 并重建）"""

    @abstractmethod
    def list_documents(self) -> list[dict]:
        """返回文档列表聚合，每项：
        {filename: str, total_chunks: int, model: str,
         chunk_size: int, chunk_overlap: int, created_at: str}
        """

    @abstractmethod
    def delete_by_source(self, filename: str) -> int:
        """按源文件名删除所有切片，返回删除数量"""
```

### 2.2 ChromaStore

位置：`services/rag_core.py`

包装 LangChain `Chroma`，collection 名固定为 `"rag_docs"`。

**构造参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `collection_name` | str | Chroma collection 名称（固定 `"rag_docs"`） |
| `persist_directory` | str | 持久化目录（`./chroma_db/rag/`） |
| `embedding_function` | callable | 外部注入的 Embedding 函数（DashScopeEmbeddings） |

**实现要点：**

- **延迟初始化**：`_ensure_db()` 在首次调用时创建 Chroma 实例，避免空库时加载失败
- **`_has_collection()`**：检查 `persist_directory/chroma.sqlite3` 是否存在
- **`add()`**：每次调用生成 UUID 作为 chunk_id，同时写入 metadata.chunk_id
- **`list_documents()`**：调用 `db.get(include=["metadatas"])` 获取全部 metadata，按 `source` 字段分组聚合，统计 total_chunks，取首个 model/created_at；旧数据缺字段时回退为 `"unknown"`/`0`
- **`delete_by_source()`**：先 `db.get(where={"source": filename})` 获取 ID 列表，再用 `_collection.delete(where={"source": {"$eq": filename}})` 执行删除；空 ID 列表直接返回 0
- **`get_all_chunks()`**：`db.get(include=["documents", "metadatas"])` 返回全部剩余切片的 `(list[Chunk], list[str])`

### 2.3 BM25Index

位置：`services/rag_core.py`

基于 `rank_bm25.BM25Okapi` + `jieba` 分词的词项检索索引。

```python
class BM25Index:
    def build(self, chunks: list[Chunk], chunk_ids: list[str]) -> None:
        """jieba.lcut → BM25Okapi 训练"""

    def save(self, path: str = "./chroma_db/rag/bm25_index.pkl") -> None:
        """pickle.dump({"chunk_ids": ..., "bm25": ...})"""

    def load(self, path: str = ...) -> bool:
        """pickle.load，文件不存在返回 False"""

    def search(self, query: str, k: int = 10) -> list[str]:
        """jieba.lcut → BM25Okapi.get_scores → top-k chunk_ids"""
```

**关键行为：**
- `build()` 和 `save()` 分离，允许构建后选择性持久化
- `load()` 返回 bool，调用方据此判断是否需要重新构建

### 2.4 Reranker

位置：`services/rag_core.py`

调 DashScope `gte-rerank` HTTP API：

```
POST https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank
Authorization: Bearer {api_keys.dashscope}

Body: {
  "model": "gte-rerank",
  "input": { "query": "...", "documents": ["候选1", "候选2", ...] },
  "parameters": { "top_n": 5 }
}

Response: {
  "output": { "results": [
    {"index": 0, "relevance_score": 0.98, "document": {"text": "..."}}
  ]}
}
```

**退避策略**：HTTP 调用失败时返回空列表，不抛异常，由调用方降级。

### 2.5 HybridRetriever

位置：`services/rag_core.py`

混合检索管线：**BM25(10) ∪ Vector(10) → 去重 → Rerank(5)**

```python
class HybridRetriever:
    def __init__(self, vector_store, bm25, reranker, embedding_fn, chunks: dict[str, Chunk]):
        ...

    def search(self, query: str, k: int = 5) -> list[tuple[str, Chunk, float]]:
        # 1. BM25 检索 10 篇
        # 2. 向量检索 10 篇
        # 3. 合并去重（BM25 优先）
        # 4. Reranker 重排取 Top K
        # 5. 降级策略：Reranker 失败 → 直接返回向量检索 TopK
```

**退避策略**：Reranker 调用失败时，直接返回向量检索的 Top K 结果，不中断请求。

### 2.6 DocumentProcessor

位置：`services/rag_service.py`

```python
class DocumentProcessor:
    @staticmethod
    def parse_txt(file_bytes: bytes) -> str:
        """UTF-8 解码 bytes 返回纯文本"""

    @staticmethod
    def chunk_text(text: str, chunk_size=500, chunk_overlap=100) -> list[Chunk]:
        """RecursiveCharacterTextSplitter 切片"""
```

**分隔符优先级**：`["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]`

### 2.7 IngestionPipeline

位置：`services/rag_service.py`

```python
class IngestionPipeline:
    def __init__(self, processor, vector_store, bm25): ...

    def preview(self, text: str, chunk_size=500) -> list[Chunk]:
        """切片后取前 5 片"""

    def ingest(self, filename: str, chunks: list[Chunk],
               model="text-embedding-v4",
               chunk_size=500, chunk_overlap=100) -> int:
        """完整入库流程"""
```

**入库流程（ingest）：**

```
1. 补充 metadata → 每片写入：
   { source: filename, chunk_index: i, total_chunks: N,
     model, chunk_size, chunk_overlap, created_at: ISO8601 }

2. 逐片生成向量 → DashScopeEmbeddings.embed_query()
   日志逐片输出 "第X片, 共Y片 正在向量化..." / "已存入向量库"
   ⚠ 同步执行，大规模文档可能耗时数秒到数十秒

3. 写入 Chroma → vector_store.add(chunks, embeddings)
   每条自动生成 UUID 作为 chunk_id，同时写入 metadata

4. 重建 BM25 → bm25.build(chunks, chunk_ids) + bm25.save()
```

### 2.8 RAGEngine

位置：`services/rag_service.py`

```python
class RAGEngine:
    def __init__(self, vector_store, bm25, reranker):
        # 启动时加载 BM25 索引
        # 重建 chunk_id → Chunk 映射
        # 构建 HybridRetriever

    def search(self, query: str, top_k=5) -> list[dict]:
        """
        混合检索。
        空库( count()==0 )时直接返回 []。
        返回格式：
        [{chunk_id, source, content, score, metadata: {chunk_index, total_chunks}}]
        """

    def delete_document(self, filename: str) -> int:
        """
        删除文档，重建 BM25。
        1. vector_store.delete_by_source(filename)
        2. if 0 → return 0
        3. get_all_chunks() → 读剩余
        4. bm25.build(remaining) + save()
        5. 更新 _chunks 映射
        6. return deleted_count
        """

    def get_stats(self) -> dict:
        """返回 {total_documents: int, total_chunks: int}"""
```

**生命周期**：`RAGEngine` 在 `novel_rag_api.py` 中作为模块级全局单例。入库或删除文档后 `_engine = None`，下次请求重建。

---

## 3. API 参考

### 3.1 通用约定

| 项目 | 规则 |
|------|------|
| 基础路径 | `/rag` |
| 认证 | 全部端点要求 `Depends(get_current_user)`（JWT Bearer Token） |
| 响应格式 | `ResponseBase(code, message, data)` |
| 错误格式 | 标准 HTTPException，`detail` 为中文描述 |
| 文件上传 | `multipart/form-data`，仅 `.txt`，≤10MB |

### 3.2 `POST /rag/upload` — 上传预览

上传文件并返回切片预览（前 5 片）。

```
Request: multipart/form-data
  file: BinaryFile (.txt, ≤10MB)

后端逻辑:
  1. 校验文件类型和大小
  2. file.read() → DocumentProcessor.parse_txt()
  3. DocumentProcessor.chunk_text(text) → 全部切片
  4. 取 chunks[:5] 作为预览
  5. 保存文件到 data/uploads/{filename}
  6. 返回预览结果

Response 200:
{
  "code": 200, "message": "success",
  "data": {
    "filename": "红楼梦.txt",
    "total_chars": 730000,
    "total_chunks": 1500,
    "preview": [
      { "index": 0, "content": "第一回 甄士隐梦幻识通灵..." },
      { "index": 1, "content": "却说封肃因听见公差传唤..." },
      ...
    ]
  }
}

Error 400: "仅支持 .txt 文件" / "文件大小超过 10MB 限制"
```

### 3.3 `POST /rag/confirm` — 确认入库

```
Request:
{
  "filename": "红楼梦.txt",                  # str
  "model": "text-embedding-v4",              # str, default "text-embedding-v4"
  "chunk_size": 500,                         # int, [100, 2000], default 500
  "chunk_overlap": 100                       # int, [0, 500], default 100
}

后端逻辑:
  1. 读取 data/uploads/{filename}
  2. DocumentProcessor.chunk_text(text, chunk_size, chunk_overlap)
  3. IngestionPipeline.ingest()
     → 补充 metadata → 逐片生成向量 → 写入 Chroma → 重建 BM25
  4. 全局 _engine = None（下次检索重建引擎）
  5. 返回入库结果

Response 200:
{
  "code": 200, "message": "success",
  "data": {
    "filename": "红楼梦.txt",
    "total_chunks": 1500,
    "model": "text-embedding-v4",
    "status": "ingested"
  }
}

Error 404: "文件不存在: {filename}"
Error 400: "文件内容为空，无法入库"
```

### 3.4 `GET /rag/models` — 模型列表

```
后端逻辑: 从 settings.rag.vector_models 读取

Response 200:
{
  "code": 200, "message": "success",
  "data": { "models": ["text-embedding-v3", "text-embedding-v4"] }
}
```

### 3.5 `POST /rag/search` — 混合检索

```
Request:
{
  "query": "黛玉葬花",          # str, min_length=1
  "top_k": 5                    # int, [1, 20], default 5
}

后端逻辑:
  1. _get_engine().search(query, top_k)
  2. 空库 → 直接返回 total=0
  3. 走 HybridRetriever BM25∪Vector→去重→Rerank

Response 200:
{
  "code": 200, "message": "success",
  "data": {
    "results": [
      {
        "chunk_id": "abc-123-def",
        "source": "红楼梦.txt",
        "content": "花谢花飞花满天，红消香断有谁怜？",
        "score": 0.92,
        "metadata": { "chunk_index": 42, "total_chunks": 1500 }
      }
    ],
    "total": 5
  }
}
```

### 3.6 `GET /rag/documents` — 文档列表

从 Chroma metadata 按 `source` 字段聚合，返回知识库中所有文档。

```
后端逻辑:
  1. engine._vector_store.list_documents()
  2. 空库 → {total: 0, documents: []}

Response 200:
{
  "code": 200, "message": "success",
  "data": {
    "total": 2,
    "documents": [
      {
        "filename": "红楼梦.txt",
        "total_chunks": 1500,
        "model": "text-embedding-v4",
        "chunk_size": 500,
        "chunk_overlap": 100,
        "created_at": "2026-05-10T12:34:56"
      },
      {
        "filename": "旧文档.txt",
        "total_chunks": 1200,
        "model": "unknown",         # 旧数据兼容
        "chunk_size": 0,
        "chunk_overlap": 0,
        "created_at": "unknown"      # 旧数据兼容
      }
    ]
  }
}
```

### 3.7 `DELETE /rag/documents/{filename}` — 删除文档

删除指定文档的所有切片并重建 BM25 索引。

```
后端逻辑:
  1. engine.delete_document(filename)
  2. 删除数量为 0 → 404
  3. 全局 _engine = None
  4. 返回删除结果

Response 200:
{
  "code": 200, "message": "success",
  "data": { "filename": "红楼梦.txt", "deleted_chunks": 1500 }
}

Response 404:
{
  "code": 404, "message": "文档不存在: 红楼梦.txt", "data": null
}
```

### 3.8 `GET /rag/stats` — 知识库统计

```
后端逻辑:
  1. engine.get_stats() → 调用 list_documents() 聚合

Response 200:
{
  "code": 200, "message": "success",
  "data": { "total_documents": 3, "total_chunks": 4200 }
}
```

---

## 4. 数据模型

### 4.1 Chunk（内部数据类）

位置：`services/rag_core.py`

```python
@dataclass
class Chunk:
    content: str
    metadata: dict
```

### 4.2 Chroma Metadata（每片持久化字段）

| 字段 | 类型 | 来源 | 必填 | 说明 |
|------|------|------|------|------|
| `source` | str | ingest | 是 | 源文件名（唯一标识一篇文档） |
| `chunk_index` | int | ingest | 是 | 该文件的切片序号（从 0 开始） |
| `total_chunks` | int | ingest | 是 | 该文件总切片数 |
| `chunk_id` | str | add | 是 | UUID，与 Chroma ID 一致 |
| `model` | str | ingest | 否 | 向量模型名，旧数据 = "unknown" |
| `chunk_size` | int | ingest | 否 | 切片大小，旧数据 = 0 |
| `chunk_overlap` | int | ingest | 否 | 切片重叠量，旧数据 = 0 |
| `created_at` | str | ingest | 否 | ISO8601 入库时间，旧数据 = "unknown" |

### 4.3 BM25 索引（磁盘持久化）

```
文件: ./chroma_db/rag/bm25_index.pkl
格式: pickle 序列化的 dict {chunk_ids: list[str], bm25: BM25Okapi}
重建时机: 每次入库（ingest）或删除文档（delete_document）后
```

### 4.4 Pydantic Schema 一览

位置：`schemas/rag_schemas.py`

```python
# ── 上传预览 ──
class PreviewItem(BaseModel):
    index: int
    content: str

class UploadResponse(BaseModel):
    filename: str
    total_chars: int
    total_chunks: int
    preview: list[PreviewItem]

# ── 确认入库 ──
class ConfirmRequest(BaseModel):
    filename: str
    model: str = "text-embedding-v4"
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)

class ConfirmResponse(BaseModel):
    filename: str
    total_chunks: int
    model: str
    status: str  # "ingested"

# ── 模型列表 ──
class ModelsResponse(BaseModel):
    models: list[str]

# ── 搜索 ──
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

class SearchItemMetadata(BaseModel):
    chunk_index: int | None = None
    total_chunks: int | None = None

class SearchItem(BaseModel):
    chunk_id: str
    source: str
    content: str
    score: float
    metadata: SearchItemMetadata

class SearchResponse(BaseModel):
    results: list[SearchItem]
    total: int

# ── 文档管理 ──
class DocumentItem(BaseModel):
    filename: str
    total_chunks: int
    model: str
    chunk_size: int = 0
    chunk_overlap: int = 0
    created_at: str

class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentItem]

class DeleteDocumentResponse(BaseModel):
    filename: str
    deleted_chunks: int

class StatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
```

---

## 5. 配置

位置：`core/settings.py` → `config.json`

```json
{
  "rag": {
    "vector_models": ["text-embedding-v3", "text-embedding-v4"],
    "rerank_model": "gte-rerank",
    "default_chunk_size": 500,
    "default_chunk_overlap": 100
  }
}
```

映射到 Pydantic：

```python
class RAGConfig(BaseModel):
    vector_models: list[str] = ["text-embedding-v3", "text-embedding-v4"]
    rerank_model: str = "gte-rerank"
    default_chunk_size: int = 500
    default_chunk_overlap: int = 100
```

DashScope API 密钥位于 `config.json.api_keys.dashscope`。

---

## 6. 前端架构

### 6.1 模块化结构

```
static/
  index.html                  — Vue 3 模板 + Element Plus
  js/app.js                   — 主入口：导入模块 → setup() → return
  js/modules/ragManager.js    — RAG 模块：状态 + 方法 + Mock 数据
```

### 6.2 模块状态（ragManager.js）

```javascript
// 上传流程
selectedFile: File | null       — 用户选择的文件对象
uploadResult: Object | null     — /rag/upload 返回的 data
previewChunks: Array            — 预览切片 [{index, content}, ...]
confirmResult: Object | null    — /rag/confirm 返回的 data

// 入库设置
vectorModels: ['text-embedding-v3', 'text-embedding-v4']
selectedModel: 'text-embedding-v3'
chunkSize: 500
chunkOverlap: 100

// 入库阶段反馈
ragLoading: false               — 全局 loading
ingestPhase: ''                 — '' | 'chunking' | 'embedding' | 'indexing'

// 搜索
searchQuery: ''
searchResults: Array            — [{source, content, score, chunk_id, metadata}, ...]
searchTotal: 0
hasSearched: false

// 文档管理
documents: Array                — [{filename, total_chunks, model, chunk_size, chunk_overlap, created_at}]
docTotal: 0
deleteLoading: false

// 库统计
stats: Object | null            — {total_documents, total_chunks}
statsLoading: false
```

### 6.3 方法

| 方法 | 触发时机 | 后端 API | 副作用 |
|------|----------|----------|--------|
| `onFileSelected(file)` | 选择文件 | 无 | 校验 .txt + ≤10MB，赋值 selectedFile |
| `doUpload()` | 点击"上传预览" | `POST /rag/upload` | 更新 uploadResult/previewChunks |
| `doConfirm()` | 点击"确认入库" | `POST /rag/confirm` | 更新 confirmResult，弹出 ElMessage.success/error，刷新文档列表 |
| `doSearch()` | 点击搜索/回车 | `POST /rag/search` | 更新 searchResults/searchTotal/hasSearched |
| `resetUpload()` | 入库成功后"继续上传" | 无 | 重置所有上传状态 |
| `fetchDocuments()` | 进入页签/入库后/删除后 | `GET /rag/documents` | 更新 documents/docTotal |
| `fetchStats()` | 进入页签/入库后/删除后 | `GET /rag/stats` | 更新 stats |
| `confirmDelete(doc)` | 点击删除按钮 | `DELETE /rag/documents/{fn}` | ElMessageBox.confirm → API → 刷新列表 |
| `formatScore(score)` | 模板内 | 无 | score(0~1) → 百分比整数 |

### 6.4 入库分阶段反馈

由于后端是同步 API（非 SSE），前端用 `setTimeout` 链模拟阶段提示：

```
doConfirm() 被调用
  → ingestPhase = 'chunking'         立即
  → setTimeout 800ms → 'embedding'   模拟切片阶段
  → setTimeout 2500ms → 'indexing'   模拟向量生成阶段
  → API 返回（实际时间取决于文档大小）
  → clearTimeout + ingestPhase = ''  结束
  → ElMessage.success('入库成功')     弹窗提示
```

### 6.5 模板结构

```
activeTab === 'ragKnowledge' 时渲染：

┌─ 知识库概览统计（可选）──────────────────────────────────┐
│ 📊 知识库概览  文档 3  |  切片 4200                     │
└──────────────────────────────────────────────────────────┘

┌─ 左列 ──────────────────────────────────────────────────┐
│ ┌─ 上传面板 ──────────────────────────────────────────┐ │
│ │  文件选择 → 上传预览 → 切片预览 → 入库设置 → 确认 │ │
│ │  状态: 未选文件 / 已选未传 / 预览后 / 已入库       │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─ 文档管理 ──────────────────────────────────────────┐ │
│ │  空状态: "知识库为空，请上传文档"                    │ │
│ │  有数据: 表格展示 filename/total_chunks/model/       │ │
│ │          created_at/删除按钮                         │ │
│ │  删除: ElMessageBox.confirm → API → 刷新列表        │ │
│ └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘

┌─ 右列 ──────────────────────────────────────────────────┐
│ ┌─ 搜索面板 ──────────────────────────────────────────┐ │
│ │  空库时: 输入框 disabled，提示"知识库为空"           │ │
│ │  有库时: 输入框 + 搜索按钮                           │ │
│ │  从未搜索: 初始提示                                  │ │
│ │  有结果: 列表（进度条/来源/内容摘要）                │ │
│ │  无结果: "未找到相关内容"                            │ │
│ └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 6.6 Mock 数据

开发模式 `useMock = true` 时使用内置 Mock 数据，不依赖后端。

```javascript
MOCK_UPLOAD = {
  code: 200, message: "success",
  data: { filename: "test_novel.txt", total_chars: 296,
          total_chunks: 1, preview: [{index: 0, content: "..."}] }
}

MOCK_CONFIRM = {
  code: 200, message: "success",
  data: { filename: "test_novel.txt", total_chunks: 2,
          model: "text-embedding-v3", status: "ingested" }
}

MOCK_SEARCH = {
  code: 200, message: "success",
  data: { results: [{chunk_id, source, content, score, metadata}], total: 2 }
}

MOCK_SEARCH_EMPTY = {
  code: 200, message: "success",
  data: { results: [], total: 0 }
}
```

---

## 7. 文件与持久化

| 路径 | 类型 | 说明 |
|------|------|------|
| `data/uploads/{filename}` | 临时 | 上传的原始文件，入库后保留（不自动清理） |
| `./chroma_db/rag/` | 持久 | Chroma SQLite 持久化目录，collection 名 `rag_docs` |
| `./chroma_db/rag/bm25_index.pkl` | 持久 | BM25Okapi 序列化索引 |

---

## 8. 设计决策记录

| # | 决策 | 理由 | 影响 |
|---|------|------|------|
| 1 | VectorStore 用 ABC 抽象 | 可替换为 Milvus 等其他向量库，业务代码不依赖特定实现 | 新增实现类需实现全部抽象方法 |
| 2 | ChromaStore 延迟初始化 | 避免空库时 Chroma 加载失败 | 第一次调用方法时才新建实例 |
| 3 | BM25 索引用 pickle 持久化 | 简单可靠，无需额外中间件 | 写入和删除后必须重建 + save() |
| 4 | Reranker 降级策略 | DashScope API 不可用时不影响检索 | HybridRetriever 的搜索方法永远不抛异常 |
| 5 | lib 文档列表从 metadata 聚合 | 无需额外维护文档表，Chroma 是唯一真实来源 | list_documents() 是全量扫描 |
| 6 | 删除用 metadata filter | 不读出再逐条删，避免大文档 OOM | Chroma 原生支持 `where` 过滤 |
| 7 | 删除后重建 BM25 | BM25 不支持增量删除 | 全量重建在大文档上可能较慢 |
| 8 | 入库阶段反馈用 setTimeout 模拟 | 后端同步 API 无法推送进度 | 阶段时间固定，与实际进度无关 |
| 9 | RAGEngine 全局单例 | 避免每次请求重建 embedding 函数和映射 | 入库/删除后设 None 触发重建 |
| 10 | 前端 Mock 数据驱动 | 不依赖后端端点可用性，前后端可并行开发 | 联调时 useMock=false 切换 |


> **版本历史**：本规约整合了 RAG 核心模块（2026-05-09）、前端界面（2026-05-09）和 V2 增强（2026-05-10）三个阶段的所有功能，替代以下原子文件：spec-rag-core.md、plan-rag-core.md、todo_rag-frontend-spec.md、plan-rag-frontend.md、tasks-rag-frontend.md、todo_rag-backend-v2.md、plan-rag-backend-v2.md、tasks-rag-backend-v2.md、todo_rag-frontend-v2.md、plan-rag-frontend-v2.md、tasks-rag-frontend-v2.md。
