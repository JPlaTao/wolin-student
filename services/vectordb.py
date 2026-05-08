"""
向量知识库单例模块

提供 Chroma 向量数据库的全局单例，供 BI Agent 等模块导入使用。
"""

import os
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from core.settings import get_settings
from utils.logger import get_logger

logger = get_logger("vectordb")

settings = get_settings()

vectordb = None
try:
    api_key = settings.api_keys.dashscope
    if not api_key:
        logger.warning("未配置 DASHSCOPE_API_KEY，知识库功能不可用")
    else:
        embeddings = DashScopeEmbeddings(model="text-embedding-v4", dashscope_api_key=api_key)
        if os.path.exists("./chroma_db") and os.path.isdir("./chroma_db"):
            vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            logger.info("向量知识库加载成功")
        else:
            logger.warning("知识库目录不存在，请先运行 build_knowledge_base() 构建")
except Exception as e:
    logger.error(f"向量知识库加载失败: {e}")
