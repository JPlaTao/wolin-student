"""
RAG 知识库请求/响应模型
"""

from pydantic import BaseModel, Field


# ── 上传预览 ────────────────────────────────────────────

class PreviewItem(BaseModel):
    index: int
    content: str


class UploadResponse(BaseModel):
    filename: str
    total_chars: int
    total_chunks: int
    preview: list[PreviewItem]


# ── 确认入库 ────────────────────────────────────────────

class ConfirmRequest(BaseModel):
    filename: str
    model: str = Field(default="text-embedding-v4")
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)


class ConfirmResponse(BaseModel):
    filename: str
    total_chunks: int
    model: str
    status: str  # "ingested"


# ── 模型列表 ────────────────────────────────────────────

class ModelsResponse(BaseModel):
    models: list[str]


# ── 搜索 ────────────────────────────────────────────────

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
