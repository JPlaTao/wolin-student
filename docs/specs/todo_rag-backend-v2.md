# Feature: RAG 知识库增强 — 文档管理 API

## Problem Statement

当前 RAG 核心模块提供了上传切片预览、确认入库、检索三个能力，但缺少两个关键的后端能力：

1. **无法查看库内文档**：没有 API 可以查询库中已入库了哪些文档。Chroma 中存着每个切片的 metadata（source、chunk_index、total_chunks），但没有任何接口把这些数据聚合为文档列表暴露给前端。用户入库后就像把文件扔进了黑箱。

2. **无法删除文档**：没有 API 可以按文档删除向量库中的切片。唯一的清理操作是 `ChromaStore.clear()`，它会删除整个集合。用户想删掉某个不需要的文档时毫无办法。

需要新增文档列表查询和按源文件删除的 API，并在基础设施层补充对应的操作方法。

## Success Metrics

- 调用文档列表 API 返回库中所有文档的汇总信息（文件名、切片数、模型、入库时间），响应时间不超过 500ms
- 删除指定文档后，Chroma 中该文档的所有切片被清除，Chunk count 正确减少
- 删除指定文档后，BM25 索引中对应的词项被移除，搜索结果不再返回已删除文档的内容
- 删除不存在的文档返回明确的 404 错误
- 空库调用列表 API 返回空数组，不报错

## User Stories

- 作为前端开发者，我调用 GET /rag/documents 即可获得知识库中所有文档的列表，含每篇的切片数和元数据
- 作为前端开发者，我调用 DELETE /rag/documents/{filename} 即可删除一篇文档及其所有切片，无需关心向量库和 BM25 的内部实现
- 作为系统维护者，我可以通过 API 了解知识库的存储状态（文档数、切片总数）

## Acceptance Criteria

- [ ] `GET /rag/documents` 返回文档列表，每个文档包含：`filename`、`chunk_count`、`model`、`created_at`
- [ ] 文档列表从 Chroma metadata 中聚合（按 `source` 字段分组计数）
- [ ] 空库时 `GET /rag/documents` 返回 `{total: 0, documents: []}`
- [ ] `DELETE /rag/documents/{filename}` 删除 Chroma 中所有 `source={filename}` 的切片
- [ ] 删除成功后 BM25 索引自动重建，不残留已删除文档的词项
- [ ] 删除不存在的文件名返回 404
- [ ] 删除成功后调用文档列表 API，该文档不再出现
- [ ] 删除成功后调用搜索 API，不返回已删除文档的内容
- [ ] 新增的 `list_documents()` 和 `delete_by_source()` 方法在 `VectorStore` ABC 中有抽象定义

## Non-Goals

- 本期不实现批量删除（一次只删一个文件）
- 本期不实现文档重命名
- 本期不实现文档库的容量限制或配额管理
- 本期不改动现有 4 个 API 的请求/响应格式

## Constraints

- `VectorStore` 抽象基类必须新增 `list_documents()` 和 `delete_by_source()` 抽象方法，实现类必须实现
- Chroma 中删除按 metadata 过滤（`{"source": filename}`），不得全量读出再逐条删
- 删除后必须重建 BM25 索引（调用 `bm25.build()` + `bm25.save()`）
- 所有新端点要求 JWT 认证（`Depends(get_current_user)`）
- API 响应格式复用项目的 `ResponseBase(code, message, data)`
- 不影响现有 `/rag/upload`、`/rag/confirm`、`/rag/models`、`/rag/search` 端点的行为
