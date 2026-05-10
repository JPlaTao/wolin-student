# Plan: RAG 知识库增强 — 后端文档管理

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────────────────────┐
│  API Layer (api/novel_rag_api.py)                                       │
│                                                                          │
│  现有端点 (不变)                       新增端点                          │
│  POST /rag/upload          GET  /rag/documents                          │
│  POST /rag/confirm         DELETE /rag/documents/{filename}             │
│  GET  /rag/models                                                        │
│  POST /rag/search                                                        │
└──────┬────────────────────────────────────────────────┬──────────────────┘
       │                                                │
┌──────▼────────────────────────────────────────────────▼──────────────────┐
│  Service Layer (services/rag_service.py)                                │
│                                                                          │
│  IngestionPipeline.ingest()        RAGEngine                            │
│  ├─ 补充 metadata 时新增:          ├─ search()                          │
│  │  model, created_at,              └─ delete_document()  ← 新增         │
│  │  chunk_size, chunk_overlap                                            │
│  └─ (其余不变)                                                          │
└──────┬────────────────────────────────────────────────┬──────────────────┘
       │                                                │
┌──────▼──────────────────┐  ┌──────────────────────────▼──────────────────┐
│  rag_core.py - 基础设施    │                                             │
│                           │                                             │
│  VectorStore (ABC) 新增:  │  BM25Index (不变)                           │
│  ├─ list_documents()     │  ├─ build()                                  │
│  └─ delete_by_source()   │  ├─ save()/load()                            │
│                           │  └─ search()                                │
│  ChromaStore 新增:        │                                             │
│  ├─ list_documents()     │  RAGEngine.delete_document() 调用流程:       │
│  ├─ delete_by_source()   │  1. ChromaStore.delete_by_source(filename)   │
│  └─ get_all_chunks()     │  2. ChromaStore.get_all_chunks()             │
│                           │  3. BM25Index.build(remaining) + save()     │
└──────┬───────────────────┘  └──────────────────────────────────────────┘
       │
┌──────▼──────┐  ┌────────────────────────┐
│ ./chroma_db │  │ bm25_index.pkl         │
│ (Chroma 持久化)│  (删除后自动重建)        │
└─────────────┘  └────────────────────────┘
```

### 关键交互流程

```
DELETE /rag/documents/{filename}
  │
  ├─ 1. _get_engine() → RAGEngine 单例
  ├─ 2. engine.delete_document(filename)
  │      ├─ vector_store.delete_by_source(filename)  → Chroma where-filter delete
  │      ├─ vector_store.get_all_chunks()             → 读取剩余 chunks
  │      ├─ bm25.build(remaining_chunks, ids)         → 重建 BM25
  │      └─ bm25.save()                              → 持久化
  ├─ 3. deleted == 0 → 404
  └─ 4. 返回 ResponseBase({filename, deleted_chunks})

GET /rag/documents
  │
  ├─ 1. engine._vector_store.list_documents()
  │      ├─ Chroma.get(include=["metadatas"]) → 全部 metadata
  │      ├─ 按 source 分组聚合
  │      └─ 返回 [{filename, total_chunks, model, chunk_size, chunk_overlap, created_at}]
  └─ 2. 返回 ResponseBase({total: N, documents: [...]})
```

## 2. 组件设计

### 2.1 `services/rag_core.py` — 基础设施层

#### VectorStore — 追加两个抽象方法

```python
@abstractmethod
def list_documents(self) -> list[dict]:
    """返回文档列表，每项 {filename, total_chunks, model, created_at}"""

@abstractmethod
def delete_by_source(self, filename: str) -> int:
    """删除指定源文件的所有切片，返回删除数量"""
```

#### ChromaStore — 新增方法

**list_documents()** — 从 Chroma metadata 按 `source` 分组聚合文档列表。支持旧数据兼容（缺 model/created_at 时显示 "unknown"）。

**delete_by_source()** — 按 `source` 过滤删除，使用 `_collection.delete(where={"source": {"$eq": filename}})` 而非全量读出再逐条删。

**get_all_chunks()** — 读取全部剩余切片用于 BM25 重建，返回 `(chunks, ids)`。

### 2.2 `services/rag_service.py` — 业务层

#### IngestionPipeline.ingest() — metadata 补充

```python
# 新增字段写入 metadata:
ch.metadata["model"] = model
ch.metadata["chunk_size"] = chunk_size
ch.metadata["chunk_overlap"] = chunk_overlap
ch.metadata["created_at"] = now  # ISO8601
```

#### RAGEngine.delete_document() — 新方法

1. `vector_store.delete_by_source(filename)` → Chroma 删除
2. `get_all_chunks()` → 读剩余
3. `bm25.build(remaining) + bm25.save()` → 重建索引
4. 更新 `_chunks` 映射
5. 返回删除数量（0 = 不存在）

## 3. API 设计

### `GET /rag/documents`

```
Response 200:
{
  "code": 200, "message": "success",
  "data": {
    "total": 2,
    "documents": [
      { "filename": "红楼梦.txt", "total_chunks": 1500,
        "model": "text-embedding-v4", "chunk_size": 500,
        "chunk_overlap": 100, "created_at": "2026-05-10T12:34:56" },
      { "filename": "旧文档.txt", "total_chunks": 1200,
        "model": "unknown", "chunk_size": 0,
        "chunk_overlap": 0, "created_at": "unknown" }
    ]
  }
}
```
空库: `{total: 0, documents: []}`

### `DELETE /rag/documents/{filename}`

```
Response 200:
{ "code": 200, "message": "success",
  "data": { "filename": "红楼梦.txt", "deleted_chunks": 1500 } }

Response 404:
{ "code": 404, "message": "文档不存在: 不存在.txt", "data": null }
```

## 4. 数据设计

### Chroma Metadata 结构（新增字段）

| 字段 | 来源 | 说明 |
|------|------|------|
| `model` | ingest 新增 | 向量模型名，旧数据 = "unknown" |
| `chunk_size` | ingest 新增 | 切片大小，旧数据 = 0 |
| `chunk_overlap` | ingest 新增 | 切片重叠量，旧数据 = 0 |
| `created_at` | ingest 新增 | 入库时间 ISO8601，旧数据 = "unknown" |

### 新增 Pydantic Schemas

```python
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
```

## 5. 文件清单

| 文件 | 改动 |
|------|------|
| `services/rag_core.py` | VectorStore 新增 2 抽象方法；ChromaStore 新增 list_documents/delete_by_source/get_all_chunks |
| `services/rag_service.py` | IngestionPipeline.ingest() 补充 4 个 metadata 字段；RAGEngine 新增 delete_document() |
| `schemas/rag_schemas.py` | 新增 DocumentItem/DocumentListResponse/DeleteDocumentResponse/StatsResponse |
| `api/novel_rag_api.py` | 新增 GET /rag/documents 和 DELETE /rag/documents/{filename} |

## 6. 验证方法

全链路 10 项测试：空库列表 → 上传 → 入库 → 列表含新文档 → 搜索可搜到 → 删除 → 确认移除 → 搜索不返回 → 404 → 旧端点回归。
