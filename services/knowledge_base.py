"""
知识库服务模块

提供向量知识库的构建和管理功能。
使用 Chroma 向量数据库存储文档嵌入，支持基于语义的内容检索。
"""

import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from core.settings import get_settings
from utils.logger import get_logger

# 获取模块专用 logger
logger = get_logger("knowledge_base")


def build_knowledge_base(docs_dir: str = "docs", persist_dir: str = "./chroma_db") -> bool:
    """
    构建向量知识库

    从指定目录加载文档（.md 和 .txt），分割为文本块，
    生成向量嵌入后存储到 Chroma 向量数据库。

    参数:
        docs_dir: 文档目录路径，默认为 "docs"
        persist_dir: 向量数据库持久化目录，默认为 "./chroma_db"

    返回:
        bool: 构建成功返回 True，失败返回 False
    """
    # 检查知识库是否已存在
    if os.path.exists(persist_dir) and os.path.isdir(persist_dir) and os.listdir(persist_dir):
        logger.info(f"知识库已存在: {persist_dir}，跳过构建")
        return True

    logger.info("开始构建知识库...")

    # 检查文档目录
    if not os.path.isdir(docs_dir):
        logger.error(f"目录不存在，无法构建知识库: {docs_dir}")
        return False

    # 加载文档
    documents = []
    for filename in os.listdir(docs_dir):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(docs_dir, filename)
            try:
                loader = TextLoader(filepath, encoding="utf-8")
                docs = loader.load()
                documents.extend(docs)
                logger.debug(f"已加载文档: {filename}")
            except Exception as e:
                logger.error(f"加载文档失败 [{filename}]: {e}")

    # 检查是否加载到文档
    if not documents:
        logger.warning("没有找到任何可加载的文档，请检查 docs/ 目录")
        return False

    logger.info(f"成功加载 {len(documents)} 个文档")

    # 分割文档为文本块
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)
    logger.info(f"文档已分割为 {len(chunks)} 个文本块")

    # 检查 API Key
    api_key = get_settings().api_keys.dashscope
    if not api_key:
        logger.error("未配置 DASHSCOPE_API_KEY，请在 config.json 中设置 api_keys.dashscope")
        return False

    # 生成嵌入并构建知识库
    try:
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=api_key
        )
        # 新版 langchain-chroma 会自动持久化，无需调用 .persist()
        Chroma.from_documents(chunks, embeddings, persist_directory=persist_dir)
        logger.info(f"知识库构建完成，保存在: {persist_dir}")
        return True
    except Exception as e:
        logger.error(f"构建知识库失败: {e}")
        return False
