"""
LangChain Agent + Tools 实现的 SQL 查询链路

用 create_agent (LangChain 1.x LangGraph 模式) + 3 个 Tool
替代 api/query_agent.py 中手写的 SQL 生成 → 校验 → 执行 → 重试 循环。

入口函数 agent_sql_query() 输出 { sql, data, count }，
与现有 _build_sql_result_response / save_turn 体系兼容。
"""

import asyncio
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy import text

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from core.settings import get_settings
from utils.logger import get_logger

settings = get_settings()
logger = get_logger("query_agent_service")


# ── 系统提示词 ──────────────────────────────────────

SYSTEM_PROMPT = """你是「沃林学生管理系统」的 SQL 查询助手。你的工作是根据用户的问题，分步生成并执行 SQL 查询。

【可用工具】
1. retrieve_schema —— 获取数据库表结构（表名、字段、类型），生成 SQL 前必须先调用
2. execute_readonly_sql —— 执行只读 SQL 查询，返回数据
3. retrieve_knowledge —— 检索知识库文档（规则、定义、政策等）

【执行流程】
第1步: 调用 retrieve_schema 了解数据库结构
第2步: 根据用户问题生成正确的 SELECT 语句
第3步: 调用 execute_readonly_sql 执行 SQL
第4步: 如果执行失败，分析错误信息并修正 SQL 后重试
第5步: 用自然语言向用户总结查询结果

【SQL 生成规则】
- 只生成 SELECT 语句，不允许任何写操作
- 所有查询必须过滤 is_deleted = 0 或 is_deleted = FALSE
- 表名均为单数（teacher 而非 teachers），不要使用复数
- stu_basic_info 是学生表，不要使用 students
- 关联查询使用 JOIN
- 聚合查询使用 GROUP BY 配合 COUNT / AVG / SUM / MAX / MIN

【数据结构参考】
- teacher: teacher_id, teacher_name, gender, phone, role, is_deleted
- class: class_id, class_name, start_time, head_teacher_id, is_deleted
- class_teacher: class_id, teacher_id (多对多关联)
- stu_basic_info: stu_id, stu_name, native_place, graduated_school, major, admission_date, graduation_date, education, age, gender, advisor_id, class_id, is_deleted
- stu_exam_record: stu_id, seq_no, grade, exam_date, is_deleted
- employment: emp_id, stu_id, stu_name, class_id, open_time, offer_time, company, salary, is_deleted"""


# ── 入口函数 ────────────────────────────────────────

async def agent_sql_query(question: str, session_id: str, db: Session) -> dict:
    """
    LangChain Agent 入口：根据用户问题生成并执行 SQL。

    Args:
        question:  用户自然语言问题
        session_id: 会话 ID（仅用于日志）
        db:         SQLAlchemy 数据库会话

    Returns:
        {"sql": str, "data": list[dict], "count": int}
        兼容现有 _build_sql_result_response / save_turn 体系

    Raises:
        HTTPException 500: Agent 执行失败时抛出，由全局异常处理器统一处理
    """
    # 结果容器（通过闭包注入工具，捕获最后执行的 SQL 和数据）
    result_store: Dict[str, Any] = {}

    # 创建 LLM 实例
    llm = _create_llm()
    logger.info(f"Agent LLM: provider={settings.llm.provider}, model={settings.llm.model}")

    # 创建工具列表
    tools = _create_tools(db, result_store)

    # 创建 Agent（LangChain 1.x LangGraph 模式）
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        name="sql_query_agent",
    )

    # 执行 Agent
    logger.info(f"Agent 开始执行: session_id={session_id}, question={question[:80]}")
    try:
        # LangGraph 状态使用 messages 键
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": question}]
        })
    except Exception as e:
        logger.error(f"Agent 执行失败: session_id={session_id}, error={e}")
        # 规范约束: Agent 执行失败抛 500，由全局异常处理器处理
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Agent SQL 查询失败: {str(e)}")

    # 从 result_store 提取 SQL 和数据
    sql = result_store.get("sql", "")
    data = result_store.get("data", [])

    count = len(data)
    logger.info(f"Agent 执行完成: session_id={session_id}, count={count}")
    return {"sql": sql, "data": data, "count": count}


# ── LLM 工厂 ────────────────────────────────────────

def _create_llm() -> ChatOpenAI:
    """根据现有配置创建 LangChain ChatOpenAI 实例"""
    provider = settings.llm.provider.lower()
    api_key_map = {
        "kimi": settings.api_keys.kimi,
        "deepseek": settings.api_keys.deepseek,
        "openai": settings.api_keys.openai,
    }
    api_key = api_key_map.get(provider, settings.api_keys.kimi)
    return ChatOpenAI(
        model=settings.llm.model,
        api_key=api_key,
        base_url=settings.llm.base_url,
        temperature=settings.llm.effective_temperature,
    )


# ── 工具工厂 ────────────────────────────────────────

def _create_tools(db: Session, result_store: Dict[str, Any]) -> list:
    """
    创建 Agent 可用工具列表。

    通过闭包将 db 和 result_store 注入工具内部，
    避免在 Tool 定义中暴露基础设施参数给 LLM。
    """

    @tool
    async def retrieve_schema(query: str = "数据库表结构 字段定义 表名") -> str:
        """
        从向量知识库检索数据库表结构信息，包括所有表名、字段名和字段类型。
        在生成 SQL 之前必须调用此工具来了解数据库结构。
        """
        # 延迟导入避免与 api/query_agent.py 的循环依赖
        from api.query_agent import vectordb, FALLBACK_SCHEMA
        from api.query_agent import similarity_search_async as _similarity_search

        if vectordb is None:
            return FALLBACK_SCHEMA
        try:
            docs = await _similarity_search(vectordb, query, k=2)
            if docs:
                context = "\n\n".join(doc.page_content for doc in docs)
                return context[:4000]
        except Exception as e:
            logger.error(f"检索表结构失败: {e}")
        return FALLBACK_SCHEMA

    @tool
    async def retrieve_knowledge(query: str) -> str:
        """
        检索知识库中的文档信息，用于查询规则、定义、政策等知识性内容。
        当用户询问"规则"、"定义"、"含义"、"说明"等知识性问题时使用。
        """
        from api.query_agent import vectordb, QueryConstants
        from api.query_agent import similarity_search_async as _similarity_search

        if vectordb is None:
            return "知识库不可用"
        try:
            docs = await _similarity_search(vectordb, query, k=3)
            if docs:
                context = "\n\n".join(doc.page_content for doc in docs)
                return context[:QueryConstants.MAX_KNOWLEDGE_CHARS]
        except Exception as e:
            logger.error(f"检索知识库失败: {e}")
        return "未找到相关知识"

    @tool
    async def execute_readonly_sql(sql: str) -> str:
        """
        执行只读 SQL 查询语句并返回结果。
        输入必须是完整的 SELECT 语句。
        执行前会自动进行安全验证（禁止 DDL/DML/注入）和表名修正。
        """
        # 延迟导入避免循环依赖
        from api.query_agent import fix_table_names, validate_sql
        from api.query_agent import safe_json_dumps as _safe_json

        # 第1步：修正表名常见拼写错误
        sql_fixed = fix_table_names(sql)

        # 第2步：安全验证（复用现有 validate_sql）
        is_valid, error_msg = validate_sql(sql_fixed)
        if not is_valid:
            logger.warning(f"Agent SQL 验证失败: {error_msg}")
            return f"SQL 验证失败: {error_msg}。请修正后重试。"

        # 第3步：执行查询
        try:
            def _sync_execute() -> list:
                result = db.execute(text(sql_fixed))
                rows = result.fetchall()
                return [dict(zip(result.keys(), row)) for row in rows] if rows else []

            data = await asyncio.to_thread(_sync_execute)
            result_store["sql"] = sql_fixed
            result_store["data"] = data
            count = len(data)
            logger.info(f"Agent SQL 执行成功: {count} 条记录")

            # 返回结果给 Agent（截断大数据量避免 Token 超限）
            if count == 0:
                return "查询成功，结果为空（0 条记录）。"
            data_json = _safe_json(data, ensure_ascii=False)
            if len(data_json) > 5000:
                return f"查询成功，共 {count} 条记录。数据量较大，样本: {data_json[:5000]}..."
            return f"查询成功，共 {count} 条记录。数据: {data_json}"
        except Exception as e:
            logger.warning(f"Agent SQL 执行失败: {e}")
            return f"SQL 执行失败: {str(e)}。请检查 SQL 语句并修正后重试。"

    return [retrieve_schema, retrieve_knowledge, execute_readonly_sql]
