from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, func, Boolean
from database import Base

class ConversationMemory(Base):
    __tablename__ = "conversation_memory"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID，用于区分不同用户/对话")
    turn_index = Column(Integer, nullable=False, comment="轮次序号，同一会话内递增")
    question = Column(Text, nullable=False, comment="用户提问的原文")
    sql_query = Column(Text, nullable=True, comment="生成的SQL语句（仅SQL意图时有值）")
    result_summary = Column(Text, nullable=True, comment="查询结果摘要（JSON格式）或完整数据（当full_data_saved=True时）")
    answer_text = Column(Text, nullable=True, comment="最终返回给用户的回答文本")
    full_data_saved = Column(Boolean, default=False, comment="是否完整保存了查询结果数据（True=完整，False=仅摘要）")
    aggregate_sql = Column(Text, nullable=True, comment="数据分析分支自动生成的聚合SQL（仅当需要聚合时）")
    embedding_vector = Column(JSON, nullable=True, comment="问题的向量表示（预留）")
    created_at = Column(DateTime, server_default=func.now(), comment="记录创建时间")