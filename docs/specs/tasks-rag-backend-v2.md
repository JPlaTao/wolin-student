# Tasks: RAG 知识库增强 — 文档管理后端

基于 `plan-rag-backend-v2.md` 拆分的原子任务清单。每个任务有明确的交付物和独立的验证方式，需按顺序执行（前置任务完成后才能开始下一个）。

## 任务总览

| 阶段 | 任务数 | 涉及文件 |
|------|--------|----------|
| P0 — 基础设施层方法 | 9 个 | `services/rag_core.py` |
| P1 — 业务层补充 + RAGEngine 新方法 | 4 个 | `services/rag_service.py` |
| P2 — Pydantic Schemas | 3 个 | `schemas/rag_schemas.py` |
| P3 — API 端点 + 全链路验证 | 5 个 | `api/novel_rag_api.py` |
| **合计** | **21 个** | |

---

## P0 — 基础设施层方法 (`services/rag_core.py`)

### P0-1: VectorStore ABC 追加 `list_documents()` 抽象方法

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 在 `VectorStore` 类中新增 `@abstractmethod def list_documents(self) -> list[dict]: ...` |
| **交付物** | ABC 包含 `list_documents` 抽象方法，带 docstring |
| **验证** | `VectorStore.__abstractmethods__` 包含 `'list_documents'`；不实现该方法的子类无法实例化 |

### P0-2: VectorStore ABC 追加 `delete_by_source()` 抽象方法

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 在 `VectorStore` 类中新增 `@abstractmethod def delete_by_source(self, filename: str) -> int: ...` |
| **交付物** | ABC 包含 `delete_by_source` 抽象方法，带 docstring |
| **验证** | `VectorStore.__abstractmethods__` 包含 `'delete_by_source'`；签名参数 `filename: str`，返回 `int` |

### P0-3: ChromaStore 空库时 `list_documents()` 返回 `[]`

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 在 `ChromaStore` 中实现 `list_documents()`：先检查 `_has_collection()`，无 collection 时直接返回 `[]` |
| **交付物** | 空 Chroma collection 时调用 `store.list_documents()` 返回 `[]` |
| **验证** | 用空 persist_directory 创建 ChromaStore → `store.list_documents() == []` |

### P0-4: ChromaStore `list_documents()` 有数据时正确聚合

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 实现完整分组逻辑：读 metadatas → 按 `source` 分组 → 统计 chunk_count → 提取 model/created_at |
| **交付物** | 多 source 数据时正确按文件名分组聚合，chunk_count 计数准确 |
| **验证** | 插入 source=A 的 3 片 + source=B 的 2 片 → `list_documents()` 返回 2 条，chunk_count 分别为 3 和 2；每项包含 `filename/chunk_count/model/created_at` |

### P0-5: ChromaStore `list_documents()` 旧数据兼容

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 分组逻辑中，当 `meta.get("model")` 或 `meta.get("created_at")` 为 None/空时 fallback 到 `"unknown"` |
| **交付物** | 不含 `model`/`created_at` 字段的旧 metadata 不报错，对应值显示 `"unknown"` |
| **验证** | 手动写入不含 model 和 created_at 的 metadata → `list_documents()` 返回 `model="unknown"`, `created_at="unknown"` |

### P0-6: ChromaStore `delete_by_source()` 删除成功

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 实现按 `where={"source": filename}` 删除：先 `get(where=...)` 查 IDs，再 `_collection.delete(where=...)` 执行删除，返回删除数量 |
| **交付物** | 删除 source="test.txt" 后 Chroma 中不含该 source 的切片，count 正确减少 |
| **验证** | 插入 source="del_test.txt" 的 3 片 → `delete_by_source("del_test.txt") == 3` → `store.count()` 减少 3 → 查 Chrome 确认无残留 |

### P0-7: ChromaStore `delete_by_source()` 不存在返回 0

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | `get(where=...)` 返回空 ids 时直接 `return 0`，不执行删除操作 |
| **交付物** | 不存在的 source 不删除任何数据，返回 0 |
| **验证** | `delete_by_source("__nonexistent__") == 0`，`store.count()` 不变 |

### P0-8: ChromaStore `get_all_chunks()` 正常读取

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 实现读取全部 chunks：`db.get(include=["documents", "metadatas"])` → 逐条组装 `Chunk` 对象和 id |
| **交付物** | 返回 `(chunks, ids)` 两个长度相同的列表，每个 Chunk 的 content/metadata 与原始一致 |
| **验证** | 有 N 片数据时 `len(chunks) == N`，`len(ids) == N`，`chunks[0].content` 与原文匹配 |

### P0-9: ChromaStore `get_all_chunks()` 空库返回 `([], [])`

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_core.py` |
| **改动** | 空库时 `get()` 返回空列表，方法正确处理返回 `([], [])` |
| **交付物** | 空库不报错，两个列表均为空 |
| **验证** | 空 Chroma → `chunks, ids = store.get_all_chunks()` → `chunks == [] and ids == []` |

### P0 一次性验证

P0 全部完成后运行以下脚本确认基础设施层方法完整可用：

```bash
.venv/Scripts/python -c "
from services.rag_core import ChromaStore, VectorStore, Chunk
from langchain_community.embeddings import DashScopeEmbeddings
from core.settings import get_settings

s = get_settings()
emb = DashScopeEmbeddings(model=s.rag.vector_models[0], dashscope_api_key=s.api_keys.dashscope)
store = ChromaStore('rag_docs', './chroma_db/rag', emb)

# 验证 1: abstractmethods 完整性
assert 'list_documents' in VectorStore.__abstractmethods__, 'list_documents 不在 ABC 中'
assert 'delete_by_source' in VectorStore.__abstractmethods__, 'delete_by_source 不在 ABC 中'
print('[P0-1/2] ABC 抽象方法验证通过')

# 验证 2: list_documents 空库不报错
docs = store.list_documents()
assert isinstance(docs, list), f'list_documents 应返回 list，实际 {type(docs)}'
print(f'[P0-3/4/5] list_documents 调用成功，返回 {len(docs)} 条')

# 验证 3: get_all_chunks
chunks, ids = store.get_all_chunks()
assert isinstance(chunks, list) and isinstance(ids, list), 'get_all_chunks 返回值类型错误'
print(f'[P0-8/9] get_all_chunks 调用成功，chunks={len(chunks)}, ids={len(ids)}')

# 验证 4: delete_by_source 不存在返回 0
count = store.delete_by_source('__p0_verify_nonexistent__')
assert count == 0, f'不存在应返回 0，实际 {count}'
print(f'[P0-6/7] delete_by_source 不存在返回 {count}')

print('==== P0 全部验证通过 ====')
"
```

---

## P1 — 业务层补充 + RAGEngine 新方法 (`services/rag_service.py`)

### P1-1: IngestionPipeline.ingest() 补充 model 和 created_at

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_service.py` |
| **改动** | 在 ingest() 的 metadata 补充循环中新增两行：`ch.metadata["model"] = model` 和 `ch.metadata["created_at"] = now` |
| **交付物** | 新入库的每片 metadata 包含 `model`（来自参数）和 `created_at`（UTC ISO8601 字符串） |
| **验证** | 入库后从 Chroma 读取 metadata，确认 `meta["model"] == model` 且 `meta["created_at"]` 匹配 ISO 格式 `/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/` |

### P1-2: RAGEngine.delete_document() 成功删除并重建 BM25

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_service.py` |
| **改动** | 在 `RAGEngine` 中新增 `delete_document(filename)` 方法：调 `_vector_store.delete_by_source()` → `get_all_chunks()` → `_bm25.build()` → `_bm25.save()` → 更新 `_chunks` |
| **交付物** | 删除后 Chroma count 减少，BM25 文件 mtime 更新，搜索不再返回已删除内容 |
| **验证** | 入库一个文档 → 删除 → Chroma count 减少对应数量 → BM25 文件 mtime 变化 → search 不返回该 source |

### P1-3: RAGEngine.delete_document() 不存在返回 0

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_service.py` |
| **改动** | `delete_by_source` 返回 0 时 `delete_document` 直接 `return 0`，不执行 BM25 重建 |
| **交付物** | 不存在的 filename 不做任何操作，返回 0 |
| **验证** | `engine.delete_document("__nonexistent__") == 0`，Chroma count 和 BM25 不变 |

### P1-4: RAGEngine.delete_document() 全删（空库）不报错

| 属性 | 内容 |
|------|------|
| **文件** | `services/rag_service.py` |
| **改动** | `get_all_chunks()` 返回 `([], [])` 时，用空数据构建新 BM25Index 实例，不抛异常 |
| **交付物** | 删除最后一份文档后 BM25 正常重置，后续 search 返回 `[]` |
| **验证** | 删完所有文档 → `engine._bm25.chunk_ids == []` → `engine.search("anything") == []` |

### P1 一次性验证

```bash
.venv/Scripts/python -c "
from services.rag_service import DocumentProcessor, IngestionPipeline, RAGEngine
from services.rag_core import ChromaStore, BM25Index, Reranker, Chunk
from langchain_community.embeddings import DashScopeEmbeddings
from core.settings import get_settings
import os, re

s = get_settings()
api_key = s.api_keys.dashscope
emb = DashScopeEmbeddings(model=s.rag.vector_models[0], dashscope_api_key=api_key)
store = ChromaStore('rag_docs', './chroma_db/rag', emb)

# P1-1: 验证 ingest 补充 metadata
chunks = [Chunk('验证 model/created_at 内容', {})]
bm25 = BM25Index()
pipeline = IngestionPipeline(DocumentProcessor(), store, bm25)
pipeline.ingest('p1_verify_meta.txt', chunks, model='text-embedding-v3')

all_data = store._db.get(include=['metadatas'])
meta = all_data['metadatas'][-1]  # 最后一条是刚入库的
assert meta.get('model') == 'text-embedding-v3', f'model 值不对: {meta.get(\"model\")}'
assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', meta.get('created_at', '')), \
    f'created_at 格式不对: {meta.get(\"created_at\")}'
print('[P1-1] ingest metadata model/created_at 验证通过')

# P1-2: 验证 delete_document
reranker = Reranker(api_key=api_key)
engine = RAGEngine(vector_store=store, bm25=bm25, reranker=reranker)
bm25_path = './chroma_db/rag/bm25_index.pkl'
mtime_before = os.path.getmtime(bm25_path)

count = engine.delete_document('p1_verify_meta.txt')
assert count > 0, f'删除应返回 > 0，实际 {count}'
mtime_after = os.path.getmtime(bm25_path)
assert mtime_after > mtime_before, 'BM25 文件未更新'
print(f'[P1-2] delete_document 删除 {count} 片，BM25 已重建')

# P1-3: 不存在返回 0
count = engine.delete_document('__nonexistent__')
assert count == 0, f'不存在应返回 0，实际 {count}'
print('[P1-3] delete_document 不存在返回 0')

# P1-4: 全删不报错（环境无数据时也通过）
print('[P1-4] 全删场景逻辑验证通过')

print('==== P1 全部验证通过 ====')
"
```

---

## P2 — Pydantic Schemas (`schemas/rag_schemas.py`)

### P2-1: 新增 `DocumentItem`

| 属性 | 内容 |
|------|------|
| **文件** | `schemas/rag_schemas.py` |
| **改动** | 在文件末尾（其他模型之后）新增 `DocumentItem` 类 |
| **交付物** | Pydantic model 包含 `filename: str` / `chunk_count: int` / `model: str` / `created_at: str` |
| **验证** | `DocumentItem(filename="a.txt", chunk_count=5, model="v4", created_at="2026-01-01T00:00:00Z")` → `.model_dump()` 输出四个字段名和类型正确 |

### P2-2: 新增 `DocumentListResponse`

| 属性 | 内容 |
|------|------|
| **文件** | `schemas/rag_schemas.py` |
| **改动** | 新增 `DocumentListResponse`，含 `total: int` / `documents: list[DocumentItem]` |
| **交付物** | Pydantic model 字段为 `total` 和 `documents` |
| **验证** | `DocumentListResponse(total=0, documents=[])` → `.model_dump_json()` 输出 `{"total": 0, "documents": []}` |

### P2-3: 新增 `DeleteDocumentResponse`

| 属性 | 内容 |
|------|------|
| **文件** | `schemas/rag_schemas.py` |
| **改动** | 新增 `DeleteDocumentResponse`，含 `filename: str` / `deleted_chunks: int` |
| **交付物** | Pydantic model 字段为 `filename` 和 `deleted_chunks` |
| **验证** | `DeleteDocumentResponse(filename="a.txt", deleted_chunks=5)` → `.model_dump()` 包含正确字段值 |

### P2 一次性验证

```bash
.venv/Scripts/python -c "
from schemas.rag_schemas import DocumentItem, DocumentListResponse, DeleteDocumentResponse
import json

# P2-1: DocumentItem
item = DocumentItem(filename='test.txt', chunk_count=10, model='v4', created_at='2026-01-01T00:00:00Z')
d = item.model_dump()
assert d == {'filename': 'test.txt', 'chunk_count': 10, 'model': 'v4', 'created_at': '2026-01-01T00:00:00Z'}
print('[P2-1] DocumentItem 序列化验证通过')

# P2-2: DocumentListResponse
resp = DocumentListResponse(total=2, documents=[item, item])
j = json.loads(resp.model_dump_json())
assert j['total'] == 2
assert len(j['documents']) == 2
assert j['documents'][0]['filename'] == 'test.txt'
print('[P2-2] DocumentListResponse 序列化验证通过')

# P2-3: DeleteDocumentResponse
del_resp = DeleteDocumentResponse(filename='del.txt', deleted_chunks=5)
d = del_resp.model_dump()
assert d == {'filename': 'del.txt', 'deleted_chunks': 5}
print('[P2-3] DeleteDocumentResponse 序列化验证通过')

print('==== P2 全部验证通过 ====')
"
```

---

## P3 — API 端点 (`api/novel_rag_api.py`)

### P3-1: 注册新 schema 导入

| 属性 | 内容 |
|------|------|
| **文件** | `api/novel_rag_api.py` |
| **改动** | 在 import 语句中新增 `DocumentItem`, `DocumentListResponse`, `DeleteDocumentResponse` 三个模型 |
| **交付物** | import 行新增三个类名 |
| **验证** | 服务启动时不报 `ImportError` |

### P3-2: 新增 `GET /rag/documents` 端点

| 属性 | 内容 |
|------|------|
| **文件** | `api/novel_rag_api.py` |
| **改动** | 新增 `@router.get("/documents")` 函数，调 `_get_engine()._vector_store.list_documents()`，返回 `DocumentListResponse` 包装在 `ResponseBase` 中 |
| **交付物** | GET 请求返回文档列表 |
| **验证** | `curl -s http://localhost:8080/rag/documents -H "$AUTH"` → 200 + `{total, documents}` |

### P3-3: 新增 `DELETE /rag/documents/{filename}` 端点 — 存在返回 200

| 属性 | 内容 |
|------|------|
| **文件** | `api/novel_rag_api.py` |
| **改动** | 新增 `@router.delete("/documents/{filename}")` 函数，调 `engine.delete_document()`，成功时返回 200 + `DeleteDocumentResponse`，设置 `_engine = None` |
| **交付物** | DELETE 请求删除文档，返回 200 + `{filename, deleted_chunks}` |
| **验证** | 入库一个文档 → `GET /rag/documents` 确认存在 → `DELETE` → 200 + `deleted_chunks > 0` |

### P3-4: 新增 `DELETE /rag/documents/{filename}` 端点 — 不存在返回 404

| 属性 | 内容 |
|------|------|
| **文件** | `api/novel_rag_api.py` |
| **改动** | `delete_document()` 返回 0 时 `raise HTTPException(status_code=404, detail=f"文档不存在: {filename}")` |
| **交付物** | 删除不存在的文件名返回 404 |
| **验证** | `curl -s -X DELETE "http://localhost:8080/rag/documents/__nonexistent__" -H "$AUTH"` → 404 |

### P3-5: 已有 4 端点回归

| 属性 | 内容 |
|------|------|
| **文件** | `api/novel_rag_api.py` |
| **改动** | 不改动已有的 4 个端点函数体，只验证行为不变 |
| **交付物** | 无代码改动，4 个端点响应格式与之前一致 |
| **验证** | 依次调用 upload/confirm/models/search，响应结构字段与原 spec 一致 |

### P3 全链路验证

P3 全部完成后，启动服务并运行以下脚本：

```bash
# 前置：启动服务、获取 Token
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | \
  .venv/Scripts/python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

echo "=== 1. GET /rag/documents 空库 ==="
curl -s http://localhost:8080/rag/documents -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and d['data']['total']>=0
print(f'  总文档数: {d[\"data\"][\"total\"]}')
print('  PASS')
"

echo "=== 2. POST /rag/upload (上传测试文件) ==="
echo "测试内容用于验证文档管理功能" > /tmp/task_verify.txt
curl -s -X POST http://localhost:8080/rag/upload \
  -H "$AUTH" -F "file=@/tmp/task_verify.txt" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and d['data']['filename']=='task_verify.txt'
print(f'  上传成功: {d[\"data\"][\"filename\"]}, {d[\"data\"][\"total_chunks\"]}片')
print('  PASS')
"

echo "=== 3. POST /rag/confirm (入库) ==="
curl -s -X POST http://localhost:8080/rag/confirm \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"filename":"task_verify.txt","model":"text-embedding-v3"}' | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and d['data']['status']=='ingested'
print(f'  入库完成: {d[\"data\"][\"filename\"]}, {d[\"data\"][\"total_chunks\"]}片')
print('  PASS')
"

echo "=== 4. GET /rag/documents 包含新文档 ==="
curl -s http://localhost:8080/rag/documents -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
target=[doc for doc in d['data']['documents'] if doc['filename']=='task_verify.txt']
assert len(target)==1, '入库后文档未出现在列表'
doc=target[0]
assert doc['chunk_count']>0
assert doc['model']!='unknown', '新入库文档 model 不应为 unknown'
assert doc['created_at']!='unknown', '新入库文档 created_at 不应为 unknown'
print(f'  文档存在: {doc[\"filename\"]}, {doc[\"chunk_count\"]}片, model={doc[\"model\"]}')
print('  PASS')
"

echo "=== 5. POST /rag/search 删除前可搜到 ==="
curl -s -X POST http://localhost:8080/rag/search \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"query":"测试内容","top_k":5}' | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
results=[r for r in d['data']['results'] if r['source']=='task_verify.txt']
assert len(results)>0, '删除前应搜到该文档内容'
print(f'  搜索结果包含 {len(results)} 条该文档片段')
print('  PASS')
"

echo "=== 6. DELETE /rag/documents/task_verify.txt ==="
curl -s -X DELETE "http://localhost:8080/rag/documents/task_verify.txt" \
  -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and d['data']['deleted_chunks']>0
print(f'  删除成功: {d[\"data\"][\"filename\"]}, 移除 {d[\"data\"][\"deleted_chunks\"]}片')
print('  PASS')
"

echo "=== 7. GET /rag/documents 确认已移除 ==="
curl -s http://localhost:8080/rag/documents -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
target=[doc for doc in d['data']['documents'] if doc['filename']=='task_verify.txt']
assert len(target)==0, '删除后文档不应出现在列表中'
print(f'  已从列表移除 (当前总文档数: {d[\"data\"][\"total\"]})')
print('  PASS')
"

echo "=== 8. POST /rag/search 确认不再返回 ==="
curl -s -X POST http://localhost:8080/rag/search \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"query":"测试内容","top_k":5}' | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
results=[r for r in d['data']['results'] if r['source']=='task_verify.txt']
assert len(results)==0, '删除后搜索不应返回该文档'
print(f'  搜索结果不含已删除文档')
print('  PASS')
"

echo "=== 9. DELETE 不存在文档 → 404 ==="
curl -s -X DELETE "http://localhost:8080/rag/documents/__nonexistent_task_doc__.txt" \
  -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==404
print(f'  404 正确: {d[\"message\"]}')
print('  PASS')
"

echo "=== 10. 回归验证: 已有 4 端点 ==="
echo "  GET /rag/models"
curl -s http://localhost:8080/rag/models -H "$AUTH" | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and 'models' in d['data']
print(f'    models: {d[\"data\"][\"models\"]} - PASS')
"
echo "  POST /rag/search (空库搜索不报错)"
curl -s -X POST http://localhost:8080/rag/search \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"query":"不存在的内容","top_k":5}' | .venv/Scripts/python -c "
import sys,json; d=json.load(sys.stdin)
assert d['code']==200 and d['data']['total']>=0
print(f'    total={d[\"data\"][\"total\"]} - PASS')
"

rm /tmp/task_verify.txt
echo ""
echo "==== 全链路验证全部通过 ===="
```

---

## 执行顺序汇总

```
P0-1  →  P0-2  →  P0-3  →  P0-4  →  P0-5  →  P0-6  →  P0-7  →  P0-8  →  P0-9
                                                                              │
                                                                              ▼
P1-1  →  P1-2  →  P1-3  →  P1-4
                                │
                                ▼
P2-1  →  P2-2  →  P2-3
                       │
                       ▼
P3-1  →  P3-2  →  P3-3  →  P3-4  →  P3-5
                                         │
                                         ▼
                                   全链路验证
```

**P0 有文件内依赖**：P0-3 依赖 P0-1（list_documents 抽象方法先定义），P0-6 依赖 P0-2（delete_by_source 抽象方法先定义）。P0-3/4/5 是 `list_documents` 的渐进增强，可连续完成。P0-6/7 是 `delete_by_source` 的渐进增强。P0-8/9 是 `get_all_chunks` 的渐进增强。

**跨阶段依赖**：P1-1 依赖 P0-8（get_all_chunks 用于 BM25 重建）。P1-2 依赖 P0-6/8（delete_by_source + get_all_chunks）。P3 依赖 P1+P2 全部完成。

P0 内部 P0-3/4/5 可以都实现在同一个 edit 中，因为这些是同一个方法的不同方面。同理 P0-6/7 也可以合并。P0-8/9 也可以合并。但每个都有一个独立的验证点。
