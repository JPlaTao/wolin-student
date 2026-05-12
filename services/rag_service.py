"""
RAG 知识库业务编排层

文档处理、入库管线、检索编排
"""

import os
from datetime import datetime
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.settings import get_settings
from services.rag_core import Chunk, ChromaStore, BM25Index, Reranker, HybridRetriever
from utils.logger import get_logger

# DashScope 是国内 API，绕过系统代理避免 Clash/V2Ray 断连
_NO_PROXY_DOMAIN = "dashscope.aliyuncs.com"


def _patch_no_proxy():
    """确保 DashScope 域名不在系统代理之后"""
    current = os.environ.get("NO_PROXY", "")
    if _NO_PROXY_DOMAIN not in current:
        os.environ["NO_PROXY"] = f"{current},{_NO_PROXY_DOMAIN}" if current else _NO_PROXY_DOMAIN

logger = get_logger("rag_service")

# ── 文档处理器 ──────────────────────────────────────────

class DocumentProcessor:
    """文档解析与切片"""

    @staticmethod
    def parse_txt(file_bytes: bytes) -> str:
        """解析 TXT bytes，返回纯文本"""
        return file_bytes.decode("utf-8")

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[Chunk]:
        """RecursiveCharacterTextSplitter 切片"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
            length_function=len,
        )
        docs = splitter.create_documents([text])
        return [Chunk(content=doc.page_content, metadata={}) for doc in docs]


# ── 入库管线 ────────────────────────────────────────────

class IngestionPipeline:
    """文档入库管线：预览 → 向量化 → 存储"""

    def __init__(self, processor: DocumentProcessor, vector_store: ChromaStore, bm25: BM25Index):
        self._processor = processor
        self._vector_store = vector_store
        self._bm25 = bm25

    def preview(self, text: str, chunk_size: int = 500) -> list[Chunk]:
        """切片后取前 5 片"""
        chunks = self._processor.chunk_text(text, chunk_size=chunk_size)
        return chunks[:5]

    def ingest(
        self,
        filename: str,
        chunks: list[Chunk],
        model: str = "text-embedding-v4",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> int:
        """
        完整入库流程：
        1. 补充 metadata（source, chunk_index, total_chunks, model, chunk_size, chunk_overlap, created_at）
        2. 逐片生成嵌入 + 日志
        3. 存入 Chroma
        4. 重建 BM25 索引
        """
        settings = get_settings()

        # 1. 补充 metadata（含模型参数和入库时间）
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for i, ch in enumerate(chunks):
            ch.metadata["source"] = filename
            ch.metadata["chunk_index"] = i
            ch.metadata["total_chunks"] = len(chunks)
            ch.metadata["model"] = model
            ch.metadata["chunk_size"] = chunk_size
            ch.metadata["chunk_overlap"] = chunk_overlap
            ch.metadata["created_at"] = now

        # 2. 生成嵌入（绕过系统代理）
        _patch_no_proxy()
        api_key = settings.api_keys.dashscope
        embedding_fn = DashScopeEmbeddings(model=model, dashscope_api_key=api_key)

        embeddings = []
        total = len(chunks)
        for i, ch in enumerate(chunks):
            logger.info(f"第{i+1}片, 共{total}片 正在向量化...")
            emb = embedding_fn.embed_query(ch.content)
            embeddings.append(emb)
            logger.info(f"第{i+1}片, 共{total}片 已存入向量库")

        # 3. 存入 Chroma
        chunk_ids = self._vector_store.add(chunks, embeddings)

        # 4. 重建 BM25 索引
        self._bm25.build(chunks, chunk_ids)
        self._bm25.save()

        return len(chunks)


# ── 检索引擎 ────────────────────────────────────────────

class RAGEngine:
    """RAG 检索引擎，提供统一检索接口"""

    def __init__(self, vector_store: ChromaStore, bm25: BM25Index, reranker: Reranker):
        self._vector_store = vector_store
        self._bm25 = bm25
        self._reranker = reranker

        # 加载已有 BM25 索引
        self._bm25.load()

        # 重建 chunks 映射：从 Chroma 读取所有文档
        self._chunks: dict[str, Chunk] = {}
        self._rebuild_chunk_map()

        # 构建 embedding_fn 用于检索（绕过系统代理）
        _patch_no_proxy()
        settings = get_settings()
        api_key = settings.api_keys.dashscope
        self._embedding_fn = DashScopeEmbeddings(
            model=settings.rag.vector_models[0],
            dashscope_api_key=api_key,
        )

        self._retriever = HybridRetriever(
            vector_store=self._vector_store,
            bm25=self._bm25,
            reranker=self._reranker,
            embedding_fn=self._embedding_fn,
            chunks=self._chunks,
        )

    def _rebuild_chunk_map(self) -> None:
        """从向量库重建 chunk_id → Chunk 映射"""
        if self._vector_store.count() == 0:
            return
        try:
            chunks, ids = self._vector_store.get_all_chunks()
            self._chunks = dict(zip(ids, chunks))
        except Exception as e:
            logger.warning(f"重建 chunk 映射失败（不影响搜索）: {e}")

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        混合检索，返回 [{chunk_id, source, content, score, metadata}, ...]
        空库时返回 []
        """
        if self._vector_store.count() == 0:
            return []

        results = self._retriever.search(query, k=top_k)

        return [
            {
                "chunk_id": cid,
                "source": chunk.metadata.get("source", ""),
                "content": chunk.content,
                "score": round(float(score), 4),
                "metadata": {
                    "chunk_index": chunk.metadata.get("chunk_index"),
                    "total_chunks": chunk.metadata.get("total_chunks"),
                },
            }
            for cid, chunk, score in results
        ]

    def delete_document(self, filename: str) -> int:
        """删除文档，重建 BM25，返回删除切片数。0 表示不存在。"""
        deleted = self._vector_store.delete_by_source(filename)
        if deleted == 0:
            return 0

        remaining_chunks, remaining_ids = self._vector_store.get_all_chunks()
        if remaining_chunks:
            self._bm25.build(remaining_chunks, remaining_ids)
        else:
            self._bm25 = BM25Index()
        self._bm25.save()
        self._chunks = dict(zip(remaining_ids, remaining_chunks))

        logger.info(
            f"RAGEngine 删除 '{filename}' 完成, "
            f"删 {deleted} 片, 剩 {len(remaining_chunks)} 片"
        )
        return deleted

    def get_stats(self) -> dict:
        """返回 {total_documents, total_chunks}"""
        docs = self._vector_store.list_documents()
        total_documents = len(docs)
        total_chunks = sum(d.get("total_chunks", 0) for d in docs)
        return {"total_documents": total_documents, "total_chunks": total_chunks}
