"""
RAG 知识库 API

POST /rag/upload   — 上传文件，返回切片预览
POST /rag/confirm  — 确认入库
GET  /rag/models   — 可用向量模型列表
POST /rag/search   — 混合检索
"""

import os

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi import status as http_status

from core.auth import get_current_user
from core.settings import get_settings
from model.user import User
from schemas.rag_schemas import (
    ConfirmRequest,
    DeleteDocumentResponse,
    DocumentItem,
    DocumentListResponse,
    ModelsResponse,
    PreviewItem,
    SearchItem,
    SearchItemMetadata,
    SearchRequest,
    SearchResponse,
    StatsResponse,
    UploadResponse,
    ConfirmResponse,
)
from schemas.response import ResponseBase
from services.rag_core import (
    ChromaStore,
    BM25Index,
    Reranker,
    _CHROMA_DB_DIR,
)
from services.rag_service import DocumentProcessor, IngestionPipeline, RAGEngine
from utils.logger import get_logger
from langchain_community.embeddings import DashScopeEmbeddings

logger = get_logger("novel_rag_api")

router = APIRouter(prefix="/rag", tags=["RAG知识库"])

UPLOAD_DIR = "data/uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# ── 全局组件（懒加载） ──────────────────────────────────

_engine: RAGEngine | None = None


def _get_engine() -> RAGEngine:
    """获取 RAGEngine 单例"""
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    api_key = settings.api_keys.dashscope

    embedding_fn = DashScopeEmbeddings(
        model=settings.rag.vector_models[0],
        dashscope_api_key=api_key,
    )
    store = ChromaStore(
        collection_name="rag_docs",
        persist_directory=_CHROMA_DB_DIR,
        embedding_function=embedding_fn,
    )
    bm25 = BM25Index()
    bm25.load()
    reranker = Reranker(api_key=api_key, model=settings.rag.rerank_model)
    _engine = RAGEngine(vector_store=store, bm25=bm25, reranker=reranker)
    return _engine


# ── 端点 ────────────────────────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    上传 TXT 文件并返回切片预览（前 5 片）。
    文件 ≤ 10MB，仅支持 .txt。
    """
    # 校验文件类型
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="仅支持 .txt 文件")

    # 读取文件内容
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    text = DocumentProcessor.parse_txt(content_bytes)
    total_chars = len(text)

    logger.info(
        f"用户 {current_user.username} 上传文件: {file.filename}, "
        f"大小={len(content_bytes)}字节, 字符数={total_chars}"
    )

    # 切片预览
    chunks = DocumentProcessor.chunk_text(text)
    preview_chunks = chunks[:5]
    total_chunks = len(chunks)

    # 保存文件
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(content_bytes)

    preview = [
        PreviewItem(index=i, content=chunk.content)
        for i, chunk in enumerate(preview_chunks)
    ]

    return ResponseBase(
        code=200,
        message="success",
        data=UploadResponse(
            filename=file.filename,
            total_chars=total_chars,
            total_chunks=total_chunks,
            preview=preview,
        ),
    )


@router.post("/confirm")
async def confirm_ingestion(
    req: ConfirmRequest,
    current_user: User = Depends(get_current_user),
):
    """
    确认入库：读取已上传文件 → 切片 → 向量化 → 存储。
    """
    file_path = os.path.join(UPLOAD_DIR, req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {req.filename}")

    with open(file_path, "rb") as f:
        content_bytes = f.read()

    text = DocumentProcessor.parse_txt(content_bytes)
    chunks = DocumentProcessor.chunk_text(
        text,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
    )

    if not chunks:
        raise HTTPException(status_code=400, detail="文件内容为空，无法入库")

    settings = get_settings()
    api_key = settings.api_keys.dashscope

    # 构建组件
    embedding_fn = DashScopeEmbeddings(
        model=req.model,
        dashscope_api_key=api_key,
    )
    store = ChromaStore(
        collection_name="rag_docs",
        persist_directory=_CHROMA_DB_DIR,
        embedding_function=embedding_fn,
    )
    bm25 = BM25Index()
    pipeline = IngestionPipeline(
        processor=DocumentProcessor(),
        vector_store=store,
        bm25=bm25,
    )

    total = pipeline.ingest(
        filename=req.filename,
        chunks=chunks,
        model=req.model,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
    )

    logger.info(
        f"用户 {current_user.username} 入库完成: {req.filename}, "
        f"共 {total} 片, model={req.model}"
    )

    # 重置引擎缓存（下次检索使用新数据）
    global _engine
    _engine = None

    return ResponseBase(
        code=200,
        message="success",
        data=ConfirmResponse(
            filename=req.filename,
            total_chunks=total,
            model=req.model,
            status="ingested",
        ),
    )


@router.get("/models")
async def list_models(
    current_user: User = Depends(get_current_user),
):
    """列出可用的向量模型"""
    models = get_settings().rag.vector_models
    return ResponseBase(
        code=200,
        message="success",
        data=ModelsResponse(models=models),
    )


@router.post("/search")
async def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    """混合检索知识库"""
    engine = _get_engine()
    results = engine.search(query=req.query, top_k=req.top_k)

    items = [
        SearchItem(
            chunk_id=r["chunk_id"],
            source=r["source"],
            content=r["content"],
            score=r["score"],
            metadata=SearchItemMetadata(
                chunk_index=r["metadata"].get("chunk_index"),
                total_chunks=r["metadata"].get("total_chunks"),
            ),
        )
        for r in results
    ]

    return ResponseBase(
        code=200,
        message="success",
        data=SearchResponse(results=items, total=len(items)),
    )


@router.get("/documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
):
    """获取知识库中文档列表"""
    engine = _get_engine()
    docs = engine._vector_store.list_documents()
    return ResponseBase(
        code=200,
        message="success",
        data=DocumentListResponse(total=len(docs), documents=[DocumentItem(**d) for d in docs]),
    )


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
):
    """获取知识库统计信息（文档总数、切片总数）"""
    engine = _get_engine()
    stats = engine.get_stats()
    return ResponseBase(
        code=200,
        message="success",
        data=StatsResponse(**stats),
    )


@router.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """删除指定文档及其所有切片"""
    engine = _get_engine()
    deleted = engine.delete_document(filename)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"文档不存在: {filename}")
    global _engine
    _engine = None
    logger.info(f"用户 {current_user.username} 删除文档: {filename}, 移除 {deleted} 片")
    return ResponseBase(
        code=200,
        message="success",
        data=DeleteDocumentResponse(filename=filename, deleted_chunks=deleted),
    )
