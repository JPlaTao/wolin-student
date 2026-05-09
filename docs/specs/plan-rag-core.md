# Plan: RAG 知识库核心模块

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────┐
│  API Layer (api/novel_rag_api.py)                        │
│  POST /rag/upload  POST /rag/confirm                    │
│  GET  /rag/models  POST /rag/search                     │
└────────┬────────────────────────┬────────────────────────┘
         │                        │
┌────────▼────────────────────────▼────────────────────────┐
│  Service Layer (services/rag_service.py)                  │
│                                                          │
│  DocumentProcessor         IngestionPipeline             │
│  ├─ parse_txt()            ├─ preview()                  │
│  └─ chunk_text()           └─ ingest()                   │
│                                                          │
│  RAGEngine                                              │
│  └─ search()                                            │
└────────┬────────────────────────┬────────────────────────┘
         │                        │
┌────────▼──────────┐  ┌─────────▼────────────────────────┐
│ rag_core.py - 基础设施                                    │
│                                                          │
│ VectorStore (ABC)     BM25Index          Reranker        │
│ └─ ChromaStore        ├─ build()         └─ rerank()     │
│    (Chroma 实现)       ├─ save()/load()                   │
│                       └─ search()        HybridRetriever  │
│                                          └─ search()     │
│                                          BM25∪Vector→Rerank│
└──────┬───────────────────┬──────────────────────────────┘
       │                   │
┌──────▼──────┐  ┌────────▼────────┐
│ ./chroma_db │  │ bm25_index.pkl  │
│ (Chroma 持久化)│  (pickle 序列化)   │
└─────────────┘  └─────────────────┘
```

## 2. 组件设计

### 2.1 `services/rag_core.py` — 基础设施层

#### VectorStore (抽象接口)

```python
from abc import ABC, abstractmethod

class VectorStore(ABC):
    """向量库抽象 — 后续可替换为 Milvus"""

    @abstractmethod
    def add(self, chunks: list["Chunk"], embeddings: list[list[float]]) -> list[str]:
        """存入向量，返回 chunk_id 列表"""

    @abstractmethod
    def search(
        self, query_embedding: list[float], k: int
    ) -> list[tuple[str, float]]:
        """返回 [(chunk_id, score), ...]"""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...
```

#### ChromaStore

- 包装 LangChain `Chroma`，collection_name 固定为 `"rag_docs"`
- 通过 `Chroma(collection_name, persist_directory, embedding_function)` 构造
- `embedding_function` 外部注入，不在内部创建

#### BM25Index

基于 `rank_bm25.BM25Okapi` + `jieba` 分词：

```python
class BM25Index:
    def build(self, chunks: list[Chunk]) -> None:
        # jieba.cut → BM25Okapi 训练

    def save(self, path: str) -> None:
        # pickle.dump

    def load(self, path: str) -> bool:
        # pickle.load，文件不存在返回 False

    def search(self, query: str, k: int = 10) -> list[str]:
        # jieba.cut → BM25Okapi.get_scores → top-k chunk_ids
```

#### Reranker

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
  "output": {
    "results": [
      {"index": 0, "relevance_score": 0.98, "document": {"text": "..."}},
      ...
    ]
  }
}
```

#### HybridRetriever

```python
class HybridRetriever:
    def __init__(self, vector_store: VectorStore, bm25: BM25Index, reranker: Reranker):
        ...

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        # 1. BM25 检索 10 篇
        bm25_ids = self.bm25.search(query, k=10)

        # 2. 向量检索 10 篇
        query_emb = self.embedding_fn.embed_query(query)
        vector_results = self.vector_store.search(query_emb, k=10)

        # 3. 合并去重（最多 20）
        candidates = dedup_and_fetch(bm25_ids, vector_results)

        # 4. 重排取 Top K
        reranked = self.reranker.rerank(query, candidates, top_k=k)
        return reranked
```

**退避策略**：重排 API 调用失败时，直接返回向量检索的 Top K 结果，不抛异常。

### 2.2 `services/rag_service.py` — 业务编排层

#### Chunk 数据模型

```python
@dataclass
class Chunk:
    content: str
    metadata: dict
    # metadata 字段：
    #   source: str        — 源文件名
    #   chunk_index: int   — 该文件内的切片序号（从 0 开始）
    #   total_chunks: int  — 该文件总切片数
```

#### DocumentProcessor

```python
class DocumentProcessor:
    def parse_txt(self, file_bytes: bytes) -> str:
        """解析 TXT，返回纯文本"""

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[Chunk]:
        """RecursiveCharacterTextSplitter 切片"""
```

分隔符优先级：`["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]`

#### IngestionPipeline

```python
class IngestionPipeline:
    def __init__(self, processor: DocumentProcessor, vector_store: VectorStore, bm25: BM25Index):
        ...

    def preview(self, text: str, chunk_size: int = 500) -> list[Chunk]:
        """切片后取前 5 片"""
        ...

    def ingest(
        self,
        filename: str,
        chunks: list[Chunk],
        model: str = "text-embedding-v4",
    ) -> int:
        """完整入库流程"""
        # 1. 补充 metadata（source, chunk_index, total_chunks）
        for i, ch in enumerate(chunks):
            ch.metadata["source"] = filename
            ch.metadata["chunk_index"] = i
            ch.metadata["total_chunks"] = len(chunks)

        # 2. 生成嵌入 + 逐片日志
        embeddings = []
        dashscope_emb = DashScopeEmbeddings(model=model, ...)
        for i, ch in enumerate(chunks):
            logger.info(f"第{i+1}片, 共{len(chunks)}片 正在向量化...")
            emb = dashscope_emb.embed_query(ch.content)
            embeddings.append(emb)
            logger.info(f"第{i+1}片, 共{len(chunks)}片 已存入向量库")

        # 3. 存入 Chroma
        chunk_ids = self.vector_store.add(chunks, embeddings)

        # 4. 重建 BM25 索引
        self.bm25.build(chunks)
        self.bm25.save("./chroma_db/bm25_index.pkl")

        return len(chunks)
```

#### RAGEngine

```python
class RAGEngine:
    def __init__(self, retriever: HybridRetriever, vector_store: VectorStore):
        ...

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        混合检索，返回：
        [{chunk_id, source, content, score, metadata: {chunk_index, total_chunks}}, ...]
        """
        if self.vector_store.count() == 0:
            return []

        results = self.retriever.search(query, k=top_k)

        return [
            {
                "chunk_id": chunk_id,
                "source": chunk.metadata.get("source", ""),
                "content": chunk.content,
                "score": round(score, 4),
                "metadata": {
                    "chunk_index": chunk.metadata.get("chunk_index"),
                    "total_chunks": chunk.metadata.get("total_chunks"),
                },
            }
            for chunk_id, chunk, score in results
        ]
```

空库时返回 `[]`，不抛异常。

## 3. API 设计

### `POST /rag/upload`

```
Request: multipart/form-data
  file: BinaryFile (.txt, ≤10MB)

Logic: 保存文件到 data/uploads/ → parse_txt → chunk_text → 取前 5 片

Response 200:
{
  "code": 200,
  "message": "success",
  "data": {
    "filename": "红楼梦.txt",
    "total_chars": 730000,
    "total_chunks": 1500,
    "preview": [
      { "index": 0, "content": "第一回 甄士隐梦幻识通灵..." },
      { "index": 1, "content": "却说封肃因听见公差传唤..." },
      { "index": 2, ... },
      { "index": 3, ... },
      { "index": 4, ... }
    ]
  }
}
```

### `POST /rag/confirm`

```
Request:
{
  "filename": "红楼梦.txt",
  "model": "text-embedding-v4",
  "chunk_size": 500,
  "chunk_overlap": 100
}

Logic:
  1. 从 data/uploads/ 读取文件
  2. chunk_text 重新切片
  3. IngestionPipeline.ingest() → 日志逐片输出
  4. 返回结果

Response 200:
{
  "code": 200,
  "message": "success",
  "data": {
    "filename": "红楼梦.txt",
    "total_chunks": 1500,
    "model": "text-embedding-v4",
    "status": "ingested"
  }
}
```

无文件时返回 404。

### `GET /rag/models`

```
Logic: 从 settings.rag.vector_models 读取

Response 200:
{
  "code": 200,
  "message": "success",
  "data": {
    "models": ["text-embedding-v3", "text-embedding-v4"]
  }
}
```

### `POST /rag/search`

```
Request:
{
  "query": "黛玉葬花",
  "top_k": 5
}

Logic: RAGEngine.search(query, top_k)

Response 200:
{
  "code": 200,
  "message": "success",
  "data": {
    "results": [
      {
        "chunk_id": "abc-123-def",
        "source": "红楼梦.txt",
        "content": "原文片段...",
        "score": 0.92,
        "metadata": { "chunk_index": 42, "total_chunks": 1500 }
      }
    ],
    "total": 5
  }
}
```

空库或异常时 `total: 0`，不抛 HTTP 错误。

所有端点要求 JWT 认证（`Depends(get_current_user)`），复用项目的 `core/auth.py`。

恢复响应格式为项目统一的 `ResponseBase(code, message, data)`。

## 4. 数据与文件管理

### 上传文件存储

| 路径 | 说明 |
|---|---|
| `data/uploads/{filename}` | 上传的原始文件，持久保存 |

### 向量库与索引

| 路径 | 说明 |
|---|---|
| `./chroma_db/`（已有） | Chroma 持久化目录，collection 名 `rag_docs` |
| `./chroma_db/bm25_index.pkl` | BM25 序列化索引 |

### Chunk metadata 结构

存入 Chroma 时每片的 metadata：

```python
{
    "chunk_id": "uuid",          # Chroma 自动生成的 ID
    "source": "红楼梦.txt",       # 源文件名
    "chunk_index": 42,           # 在该文件内的序号
    "total_chunks": 1500,        # 该文件总切片数
}
```

## 5. 配置变更

`config.json` 新增节：

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

`core/settings.py` 新增：

```python
class RAGConfig(BaseModel):
    vector_models: list[str] = Field(default=["text-embedding-v3", "text-embedding-v4"])
    rerank_model: str = Field(default="gte-rerank")
    default_chunk_size: int = Field(default=500)
    default_chunk_overlap: int = Field(default=100)

class Settings(BaseModel):
    ...
    rag: RAGConfig = Field(default_factory=RAGConfig)
```

## 6. 依赖

`requirements.txt` 新增：

```
rank_bm25>=0.2.0
jieba>=0.42.1
```

## 7. 文件清单

### 新建

| 文件 | 职责 |
|---|---|
| `services/rag_core.py` | VectorStore ABC + ChromaStore + BM25Index + Reranker + HybridRetriever |
| `services/rag_service.py` | DocumentProcessor + IngestionPipeline + RAGEngine |
| `schemas/rag_schemas.py` | 请求/响应 Pydantic 模型 |

### 重写

| 文件 | 改动 |
|---|---|
| `api/novel_rag_api.py` | 原有 `/novel/search` 删除，改为 `/rag/upload` `/rag/confirm` `/rag/models` `/rag/search` |

### 修改

| 文件 | 改动 |
|---|---|
| `main.py` | 移除 `build_novel_kb()` 调用；注册 `novel_rag_api.router`（保留） |
| `core/settings.py` | 新增 `RAGConfig` |
| `requirements.txt` | 新增 `rank_bm25`、`jieba` |

### 删除

| 文件 | 原因 |
|---|---|
| `services/novel_rag.py` | 被 `rag_core.py` + `rag_service.py` 取代 |
| `data/novels/` | 改为 `data/uploads/`，文件由前端上传 |

## 8. 原子任务清单

每个任务有明确的交付物和验证方式，需按序号顺序执行（依赖前置任务完成）。

### P0 — 基础设施准备

| # | 任务 | 文件 | 交付物 | 验证方式 |
|---|------|------|--------|----------|
| 1 | 新增 `RAGConfig` | `core/settings.py` | `Settings.rag` 字段，含 `vector_models`/`rerank_model`/`default_chunk_size`/`default_chunk_overlap` | `get_settings().rag.vector_models == ["text-embedding-v3", "text-embedding-v4"]` |
| 2 | 新增 `rag` 配置节 | `config.json` | `{ rag: { vector_models: [...], rerank_model: "gte-rerank", default_chunk_size: 500, default_chunk_overlap: 100 } }` | Settings 加载后 rag 字段非空 |
| 3 | 新增 Python 依赖 | `requirements.txt` | 添加 `rank_bm25>=0.2.0` 和 `jieba>=0.42.1` | `.venv/Scripts/python -c "import rank_bm25; import jieba"` 无报错 |
| 4 | 创建上传目录 | — | `data/uploads/` 目录存在 | `ls data/uploads/` 存在 |
| 5 | 初始化上传目录 gitkeep | `data/uploads/.gitkeep` | 空占位文件，确保空目录被版本控制 | 文件存在 |

### P1 — 基础设施层 (`services/rag_core.py`)

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 6 | `VectorStore` 抽象基类 + `Chunk` 数据类 | ABC 含 `add/search/count/clear` 四个抽象方法；`@dataclass Chunk` 含 `content: str` / `metadata: dict` | `VectorStore` 不能直接实例化；`Chunk("a", {})` 可构造 |
| 7 | `ChromaStore` 实现 | 包装 langchain `Chroma`，collection 名 `rag_docs`，`embedding_function` 外部注入 | `store.add([chunk], [emb])` → 返回 id 列表；`store.count()` 递增；`store.clear()` 归零 |
| 8 | `BM25Index` 实现 | `jieba` 分词 + `rank_bm25.BM25Okapi`，`build/save/load/search` 完整 | `bm25.build(chunks)` → `bm25.search("query")` 返回匹配 id 列表；save/load pickle 后搜索结果一致 |
| 9 | `Reranker` 实现 | DashScope `gte-rerank` HTTP API 客户端，`rerank(query, documents, top_k) → list[(text, score)]` | mock HTTP 200 响应 → 返回排序后的 `(text, score)` 列表 |
| 10 | `HybridRetriever` 实现 | BM25(10) ∪ Vector(10) → 去重 → Reranker(5) 管线，含退避策略 | BM25+Vector 有重叠时返回 ≤10 条；Reranker 不可用时降级到 Vector TopK |

验证脚本（任务 10 完成后一次性验证 P1）：

```bash
.venv/Scripts/python -c "
from services.rag_core import Chunk, ChromaStore, BM25Index, Reranker, HybridRetriever
# 验证导入无报错
print('P1 全部组件导入成功')
"
```

### P2 — 业务编排层 (`services/rag_service.py`)

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 11 | `DocumentProcessor` — `parse_txt()` | 读取 bytes 返回纯文本 str | 输入 bytes → 输出与原文完全一致，无 BOM/编码问题 |
| 12 | `DocumentProcessor` — `chunk_text()` | `RecursiveCharacterTextSplitter` 切片，分隔符优先 `["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]` | 500 字短文 → 切 1 片不丢内容；2000 字长文 → 切多片，相邻片段 overlap=100 |
| 13 | `IngestionPipeline` — `preview()` | 切片后返回前 5 片（不超过 5） | 100 片的总文档 → 返回 5 片；2 片的文档 → 返回 2 片 |
| 14 | `IngestionPipeline` — `ingest()` | 完整入库：补充 metadata(souce/chunk_index/total_chunks) → 逐片 embedding（每片输出"第X片, 共Y片 正在向量化/已存入向量库"日志）→ Chroma 存储 → BM25 重建并持久化 | 日志逐片输出，格式匹配 spec；`vector_store.count()` 正确递增；`./chroma_db/bm25_index.pkl` 存在 |
| 15 | `RAGEngine` — `search()` | 调用 HybridRetriever，返回 `[{chunk_id, source, content, score, metadata}]`；空库返回 `[]` | 空库搜索 → `[]`；有数据搜索 → 结果含完整字段 |

验证脚本（任务 15 完成后一次性验证 P2）：

```bash
.venv/Scripts/python -c "
from services.rag_service import DocumentProcessor, IngestionPipeline, RAGEngine
from services.rag_core import ChromaStore, BM25Index
# 验证导入
print('P2 全部组件导入成功')
"
```

### P3 — API 层

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 16 | `schemas/rag_schemas.py` | 所有请求/响应 Pydantic 模型（`UploadResponse`/`ConfirmRequest`/`ConfirmResponse`/`ModelsResponse`/`SearchRequest`/`SearchResponse`/`SearchItem`） | 每个模型可用示例数据构造，序列化后字段名和类型匹配 spec |
| 17 | `POST /rag/upload` | 接收 multipart file(.txt, ≤10MB) → 保存到 `data/uploads/` → `parse_txt` → `chunk_text` → 返回 preview(5片) | `curl -F "file=@test.txt"` → 200 + `{preview: [{index, content}, ...]}` |
| 18 | `POST /rag/confirm` | 读取已上传文件 → 重新切片 → `IngestionPipeline.ingest()` → 返回入库结果 | `curl -X POST -H "Content-Type: application/json" -d '{"filename":"test.txt"}'` → 200 + `{status: "ingested", total_chunks: N}` |
| 19 | `GET /rag/models` | 从 `settings.rag.vector_models` 返回可用模型列表 | `curl` → 200 + `{models: ["text-embedding-v3", "text-embedding-v4"]}` |
| 20 | `POST /rag/search` | 混合检索，返回排序后的结果列表；空库返回 `{total: 0}` | `curl -X POST -d '{"query":"test", "top_k":5}'` → 200 + `{results: [...], total: N}` |

### P4 — 清理与验证

| # | 任务 | 交付物 | 验证方式 |
|---|------|--------|----------|
| 21 | 清理 `main.py` | 移除 `from services.novel_rag import build_novel_kb` 和 `build_novel_kb()` 调用；保留 `novel_rag_api.router` 注册 | 服务启动无报错，`/rag/models` 正常返回 |
| 22 | 删除过期文件 | 删除 `services/novel_rag.py`、`data/novels/`（如存在） | 文件不再存在；`git status` 确认删除 |
| 23 | 完整冒烟测试 | 上传→预览→确认→搜索→空库搜索 全链路 | 执行验证小节全部 6 条用例 |

## 9. 验证

### 9.1 全链路冒烟测试 (任务 23)

```bash
# 前置：获取 JWT Token
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | \
  .venv/Scripts/python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

AUTH="Authorization: Bearer $TOKEN"

# 测试 1: 切片 — 上传已知内容的 TXT 文件
echo "测试1: 上传文件 → 切片预览"
echo "黛玉葬花是红楼梦中的经典情节。" > /tmp/test_rag.txt
curl -s -X POST http://localhost:8080/rag/upload \
  -H "$AUTH" \
  -F "file=@/tmp/test_rag.txt" | .venv/Scripts/python -m json.tool
# 预期: 200, preview 数组, 每片 content 无乱码

# 测试 2: 入库 — 确认入库 + 检查日志
echo "测试2: 确认入库"
curl -s -X POST http://localhost:8080/rag/confirm \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test_rag.txt","model":"text-embedding-v3","chunk_size":500,"chunk_overlap":100}' | .venv/Scripts/python -m json.tool
# 预期: status=ingested, total_chunks=N
# 检查后端日志包含 "第1片, 共N片 正在向量化"

# 测试 3: 检索
echo "测试3: 搜索相关内容"
curl -s -X POST http://localhost:8080/rag/search \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"query":"黛玉葬花","top_k":5}' | .venv/Scripts/python -m json.tool
# 预期: results 非空, 每个结果含 chunk_id/source/content/score/metadata

# 测试 4: 空库搜索（先清空，或重启后首次搜索）
# 预期: total=0, results=[]

# 测试 5: 引用 — 检查结果中的 chunk_id 格式
# 预期: chunk_id 为非空字符串

# 清理
rm /tmp/test_rag.txt
```

### 9.2 回归验证

| 用例 | 预期 | 验证方式 |
|------|------|----------|
| 黛玉智能对话正常 | SSE 流式回复无报错 | 前端页面发一条消息 |
| BI Agent 正常 | 数据分析对话无报错 | 前端页面发一条消息 |
| 文生图正常 | 图片生成正常 | `POST /api/image-gen` |
| 原有知识库不受影响 | 已有 Chroma collection 数据不变 | `vector_store.count()` 与原值一致 |
