"""
RAG 知识库基础设施层

向量库抽象接口 + Chroma 实现 + BM25 索引 + 重排序器 + 混合检索器
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
import pickle
from typing import Optional

import httpx
import jieba
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi

from utils.logger import get_logger

logger = get_logger("rag_core")

_CHROMA_DB_DIR = "./chroma_db/rag"
_BM25_INDEX_PATH = "./chroma_db/rag/bm25_index.pkl"


# ── 数据模型 ─────────────────────────────────────────────

@dataclass
class Chunk:
    content: str
    metadata: dict


# ── 向量库抽象 ───────────────────────────────────────────

class VectorStore(ABC):
    """向量库抽象接口 — 后续可替换为 Milvus"""

    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
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

    @abstractmethod
    def list_documents(self) -> list[dict]:
        """返回文档列表，每项 {filename, total_chunks, model, created_at}"""

    @abstractmethod
    def delete_by_source(self, filename: str) -> int:
        """删除指定源文件的所有切片，返回被删除的切片数量"""



# ── BM25 索引 ───────────────────────────────────────────

class BM25Index:
    """基于 BM25Okapi + jieba 分词的词项检索索引"""

    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.chunk_ids: list[str] = []

    def build(self, chunks: list[Chunk], chunk_ids: list[str]) -> None:
        """用已有 chunk_id 构建 BM25 索引"""
        self.chunk_ids = chunk_ids
        tokenized = [list(jieba.lcut(c.content)) for c in chunks]
        self.bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25 索引构建完成，共 {len(chunks)} 片")

    def search(self, query: str, k: int = 10) -> list[str]:
        """返回 top-k chunk_id 列表"""
        if self.bm25 is None:
            return []
        tokenized = list(jieba.lcut(query))
        scores = self.bm25.get_scores(tokenized)
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]
        return [self.chunk_ids[i] for i in top_indices]

    def save(self, path: str = _BM25_INDEX_PATH) -> None:
        with open(path, "wb") as f:
            pickle.dump({"chunk_ids": self.chunk_ids, "bm25": self.bm25}, f)
        logger.info(f"BM25 索引已持久化: {path}")

    def load(self, path: str = _BM25_INDEX_PATH) -> bool:
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.chunk_ids = data["chunk_ids"]
            self.bm25 = data["bm25"]
            logger.info(f"BM25 索引已加载: {path} (共 {len(self.chunk_ids)} 片)")
            return True
        except FileNotFoundError:
            logger.warning(f"BM25 索引文件不存在: {path}")
            return False


# ── Chroma 实现 ─────────────────────────────────────────

class ChromaStore(VectorStore):
    """基于 LangChain Chroma 的向量库实现（延迟初始化）"""

    def __init__(self, collection_name: str, persist_directory: str, embedding_function):
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._embedding_function = embedding_function
        self._db: Optional[Chroma] = None

    def _ensure_db(self) -> Chroma:
        """延迟初始化：首次调用时创建 Chroma 实例"""
        if self._db is None:
            self._db = Chroma(
                collection_name=self._collection_name,
                persist_directory=self._persist_directory,
                embedding_function=self._embedding_function,
            )
        return self._db

    def _has_collection(self) -> bool:
        """检查磁盘上是否存在 Chroma 数据目录"""
        sqlite_path = os.path.join(self._persist_directory, "chroma.sqlite3")
        return os.path.isfile(sqlite_path)

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        """存入向量，返回 chunk_id 列表（ID 同时写入 metadata.chunk_id）"""
        import uuid
        texts = [c.content for c in chunks]
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [dict(c.metadata) for c in chunks]
        for i, mid in enumerate(ids):
            metadatas[i]["chunk_id"] = mid
        db = self._ensure_db()
        result_ids = db.add_texts(texts, metadatas, embeddings=embeddings, ids=ids)
        return result_ids

    def search(self, query_embedding: list[float], k: int) -> list[tuple[str, float]]:
        db = self._ensure_db()
        docs_and_scores = db.similarity_search_by_vector_with_relevance_scores(
            query_embedding, k=k
        )
        seen = set()
        out = []
        for doc, score in docs_and_scores:
            cid = doc.metadata.get("chunk_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                out.append((cid, float(score)))
        if not out:
            for i, doc in enumerate(docs_and_scores):
                out.append((f"{self._collection_name}_{i}", float(doc[1])))
        return out

    def count(self) -> int:
        if self._db is None and not self._has_collection():
            return 0
        return self._ensure_db()._collection.count()

    def clear(self) -> None:
        if self._db is not None:
            try:
                self._db.delete_collection()
            except Exception:
                pass
            self._db = None

    def list_documents(self) -> list[dict]:
        """从 Chroma metadata 按 source 分组聚合文档列表"""
        if not self._has_collection():
            return []
        all_data = self._ensure_db().get(include=["metadatas"])
        metadatas = all_data.get("metadatas", [])
        if not metadatas:
            return []

        doc_map: dict[str, dict] = {}
        for meta in metadatas:
            source = meta.get("source", "unknown")
            if source not in doc_map:
                doc_map[source] = {
                    "filename": source,
                    "total_chunks": 0,
                    "model": "unknown",
                    "chunk_size": meta.get("chunk_size", 0),
                    "chunk_overlap": meta.get("chunk_overlap", 0),
                    "created_at": "unknown",
                }
            doc_map[source]["total_chunks"] += 1
            if doc_map[source]["model"] == "unknown" and meta.get("model"):
                doc_map[source]["model"] = meta["model"]
            if meta.get("chunk_size"):
                doc_map[source]["chunk_size"] = meta["chunk_size"]
            if meta.get("chunk_overlap"):
                doc_map[source]["chunk_overlap"] = meta["chunk_overlap"]
            ts = meta.get("created_at", "")
            if ts and (
                doc_map[source]["created_at"] == "unknown"
                or ts < doc_map[source]["created_at"]
            ):
                doc_map[source]["created_at"] = ts
        return list(doc_map.values())

    def delete_by_source(self, filename: str) -> int:
        """按 source 删除所有切片，返回删除数量"""
        db = self._ensure_db()
        results = db.get(where={"source": filename}, include=[])
        ids = results.get("ids", [])
        if not ids:
            return 0
        self._db._collection.delete(where={"source": {"$eq": filename}})
        logger.info(f"ChromaStore 删除 source={filename}, 共 {len(ids)} 片")
        return len(ids)

    def get_all_chunks(self) -> tuple[list[Chunk], list[str]]:
        """读取 Chroma 全部切片用于 BM25 重建，返回 (chunks, ids)"""
        db = self._ensure_db()
        results = db.get(include=["documents", "metadatas"])
        chunks: list[Chunk] = []
        ids: list[str] = []
        for i, doc in enumerate(results.get("documents", []) or []):
            if doc is not None:
                meta = (results.get("metadatas") or [{}])[i] or {}
                chunks.append(Chunk(content=doc, metadata=meta))
                ids.append(results["ids"][i])
        return chunks, ids


# ── Milvus 实现 ─────────────────────────────────────────

class MilvusStore(VectorStore):
    """基于 pymilvus MilvusClient 的向量库实现（延迟连接）"""

    def __init__(self, collection_name: str, uri: str, dim: int, token: str = ""):
        self._collection_name = collection_name
        self._uri = uri
        self._dim = dim
        self._token = token
        self._client = None

    def _ensure_client(self) -> "MilvusClient":
        """确保已连接（不自动创建集合）"""
        if self._client is None:
            from pymilvus import MilvusClient
            self._client = MilvusClient(uri=self._uri, token=self._token or None)
        return self._client

    def _ensure_collection(self) -> "MilvusClient":
        """确保连接且集合存在"""
        client = self._ensure_client()
        if not client.has_collection(self._collection_name):
            self._create_collection()
        return client

    def _has_collection(self) -> bool:
        if self._client is None:
            return False
        return self._client.has_collection(self._collection_name)

    def _create_collection(self) -> None:
        from pymilvus import MilvusClient, DataType

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", datatype=DataType.VARCHAR, is_primary=True, max_length=36)
        schema.add_field("vector", datatype=DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field("source", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field("chunk_index", datatype=DataType.INT64)
        schema.add_field("total_chunks", datatype=DataType.INT64)
        schema.add_field("model", datatype=DataType.VARCHAR, max_length=50)
        schema.add_field("chunk_size", datatype=DataType.INT64)
        schema.add_field("chunk_overlap", datatype=DataType.INT64)
        schema.add_field("created_at", datatype=DataType.VARCHAR, max_length=30)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type="COSINE",
            index_type="HNSW",
            params={"M": 16, "efConstruction": 200},
        )

        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level="Strong",
        )
        logger.info(f"Milvus collection '{self._collection_name}' 已创建, dim={self._dim}")

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        import uuid
        client = self._ensure_collection()
        data = []
        ids = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            cid = str(uuid.uuid4())
            ids.append(cid)
            meta = chunk.metadata
            data.append({
                "id": cid,
                "vector": emb,
                "text": chunk.content,
                "source": meta.get("source", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "total_chunks": meta.get("total_chunks", 0),
                "model": meta.get("model", ""),
                "chunk_size": meta.get("chunk_size", 0),
                "chunk_overlap": meta.get("chunk_overlap", 0),
                "created_at": meta.get("created_at", ""),
            })
            chunk.metadata["chunk_id"] = cid
        client.insert(self._collection_name, data)
        logger.info(f"MilvusStore 插入 {len(data)} 条记录")
        return ids

    def search(self, query_embedding: list[float], k: int) -> list[tuple[str, float]]:
        client = self._ensure_collection()
        results = client.search(
            collection_name=self._collection_name,
            data=[query_embedding],
            limit=k,
            metric_type="COSINE",
            output_fields=["id"],
        )
        out = []
        if results and results[0]:
            for hit in results[0]:
                out.append((hit["id"], float(hit["distance"])))
        return out

    def count(self) -> int:
        client = self._ensure_client()
        if not client.has_collection(self._collection_name):
            return 0
        result = client.query(
            collection_name=self._collection_name,
            output_fields=["count(*)"],
        )
        return result[0]["count(*)"] if result else 0

    def clear(self) -> None:
        if self._client is not None:
            self._client.drop_collection(self._collection_name)
            self._client = None
            logger.info(f"Milvus collection '{self._collection_name}' 已清除")

    def list_documents(self) -> list[dict]:
        if not self._has_collection():
            return []
        client = self._ensure_collection()
        results = client.query(
            collection_name=self._collection_name,
            output_fields=["source", "chunk_index", "total_chunks",
                           "model", "chunk_size", "chunk_overlap", "created_at"],
            limit=10000,
        )
        doc_map: dict[str, dict] = {}
        for row in results:
            source = row.get("source", "unknown")
            if source not in doc_map:
                doc_map[source] = {
                    "filename": source,
                    "total_chunks": 0,
                    "model": "unknown",
                    "chunk_size": row.get("chunk_size", 0) or 0,
                    "chunk_overlap": row.get("chunk_overlap", 0) or 0,
                    "created_at": "unknown",
                }
            doc_map[source]["total_chunks"] += 1
            if doc_map[source]["model"] == "unknown" and row.get("model"):
                doc_map[source]["model"] = row["model"]
            if row.get("chunk_size"):
                doc_map[source]["chunk_size"] = row["chunk_size"]
            if row.get("chunk_overlap"):
                doc_map[source]["chunk_overlap"] = row["chunk_overlap"]
            ts = row.get("created_at", "")
            if ts and (doc_map[source]["created_at"] == "unknown" or ts < doc_map[source]["created_at"]):
                doc_map[source]["created_at"] = ts
        return list(doc_map.values())

    def delete_by_source(self, filename: str) -> int:
        client = self._ensure_collection()
        count_res = client.query(
            collection_name=self._collection_name,
            filter=f'source == "{filename}"',
            output_fields=["count(*)"],
        )
        to_delete = count_res[0]["count(*)"] if count_res else 0
        if to_delete == 0:
            return 0
        client.delete(
            collection_name=self._collection_name,
            filter=f'source == "{filename}"',
        )
        logger.info(f"MilvusStore 删除 source={filename}, 共 {to_delete} 片")
        return to_delete

    def get_all_chunks(self) -> tuple[list[Chunk], list[str]]:
        client = self._ensure_collection()
        results = client.query(
            collection_name=self._collection_name,
            output_fields=["id", "text", "source", "chunk_index",
                           "total_chunks", "model", "chunk_size",
                           "chunk_overlap", "created_at"],
            limit=10000,
        )
        chunks: list[Chunk] = []
        ids: list[str] = []
        for row in results:
            meta = {
                "source": row.get("source", ""),
                "chunk_index": row.get("chunk_index"),
                "total_chunks": row.get("total_chunks"),
                "model": row.get("model", ""),
                "chunk_size": row.get("chunk_size", 0),
                "chunk_overlap": row.get("chunk_overlap", 0),
                "created_at": row.get("created_at", ""),
                "chunk_id": row["id"],
            }
            chunks.append(Chunk(content=row["text"], metadata=meta))
            ids.append(row["id"])
        return chunks, ids


# ── 重排序器 ────────────────────────────────────────────

class Reranker:
    """基于 DashScope gte-rerank 的重排序器"""

    def __init__(self, api_key: str, model: str = "gte-rerank"):
        self._api_key = api_key
        self._model = model
        self._url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

    def rerank(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[str, float]]:
        """
        对候选文档重排序，返回 [(text, score), ...]
        失败时返回空列表（调用方降级）
        """
        if not documents:
            return []

        payload = {
            "model": self._model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": top_k},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = httpx.post(self._url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("output", {}).get("results", [])
            return [
                (item["document"]["text"], item["relevance_score"])
                for item in sorted(results, key=lambda x: x["relevance_score"], reverse=True)
            ]
        except Exception as e:
            logger.warning(f"Reranker 调用失败: {e}，降级到原始排序")
            return []


# ── 混合检索器 ──────────────────────────────────────────

class HybridRetriever:
    """BM25 ∪ 向量 → 去重 → 重排序 混合检索"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25: BM25Index,
        reranker: Reranker,
        embedding_fn,
        chunks: dict[str, Chunk],  # chunk_id → Chunk 映射
    ):
        self._vector_store = vector_store
        self._bm25 = bm25
        self._reranker = reranker
        self._embedding_fn = embedding_fn
        self._chunks = chunks

    def search(self, query: str, k: int = 5) -> list[tuple[str, Chunk, float]]:
        """
        混合检索，返回 [(chunk_id, Chunk, score), ...]
        退避策略：重排失败时返回向量检索 TopK
        """
        # 1. BM25 检索 10 篇
        bm25_ids = self._bm25.search(query, k=10)

        # 2. 向量检索 10 篇
        query_emb = self._embedding_fn.embed_query(query)
        vector_results = self._vector_store.search(query_emb, k=10)

        # 3. 合并去重（按 BM25 → 向量顺序，保留首次出现的 id）
        seen = set()
        candidate_ids = []
        for cid in bm25_ids:
            if cid not in seen:
                seen.add(cid)
                candidate_ids.append(cid)
        for cid, _ in vector_results:
            if cid not in seen:
                seen.add(cid)
                candidate_ids.append(cid)

        # 4. 获取候选文档文本
        candidates = [self._chunks[cid] for cid in candidate_ids if cid in self._chunks]
        if not candidates:
            return []

        candidate_texts = [c.content for c in candidates]

        # 5. 重排取 Top K
        reranked = self._reranker.rerank(query, candidate_texts, top_k=k)

        if reranked:
            # 映射回 chunk_id
            text_to_id = {c.content: cid for cid, c in self._chunks.items()}
            text_to_chunk = {c.content: c for c in candidates}
            result = []
            for text, score in reranked:
                cid = text_to_id.get(text, "")
                chunk = text_to_chunk.get(text)
                if chunk:
                    result.append((cid, chunk, score))
            return result

        # 退避：重排失败，直接返回向量检索 TopK
        logger.info("HybridRetriever 降级：使用向量检索结果")
        fallback = []
        for cid, score in vector_results[:k]:
            chunk = self._chunks.get(cid)
            if chunk:
                fallback.append((cid, chunk, score))
        return fallback
