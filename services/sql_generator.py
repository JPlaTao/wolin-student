"""SQL 生成、验证、修复"""
import re
import asyncio
from typing import Optional, List

import sqlparse
from sqlparse import tokens
from sqlalchemy import text
from langchain_chroma import Chroma
from langchain_core.documents import Document

from core.settings import get_settings
from services.llm_service import get_llm_client, get_llm_model, get_llm_temperature
from services.intent_classifier import sanitize_prompt_input
from utils.logger import get_logger
from prompts.loader import load_prompt

logger = get_logger("sql_generator")

# ---------- 备用表结构 ----------
# 版本: v1.1 | 最后同步: 2026-04-22 | 源: database_init_test.sql
FALLBACK_SCHEMA = """
数据库表结构（简化版）：
- teacher: teacher_id, teacher_name, gender, phone, role, is_deleted (BOOLEAN)
- class: class_id, class_name, start_time, head_teacher_id, is_deleted (BOOLEAN)
- class_teacher: class_id, teacher_id (多对多关联表，关联班级和授课教师)
- stu_basic_info: stu_id, stu_name, native_place, graduated_school, major, admission_date, graduation_date, education, age, gender, advisor_id, class_id, is_deleted (BOOLEAN)
- stu_exam_record: stu_id, seq_no, grade, exam_date, is_deleted (INT, 0=未删除)
- employment: emp_id, stu_id, stu_name, class_id, open_time, offer_time, company, salary, is_deleted (BOOLEAN)

重要规则：
- 所有查询必须过滤 is_deleted = 0 或 False（成绩表用 is_deleted = 0）
- 表名均为单数形式，不要使用复数
- 只生成 SELECT 语句
- 查询班级对应的教师时，需要通过 class_teacher 关联表
"""

AGGREGATE_SQL_PROMPT = load_prompt("aggregate_sql")


def fix_table_names(sql: str) -> str:
    """修正 SQL 中的表名"""
    sql = re.sub(r'\bteachers\b', 'teacher', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bstudents\b', 'stu_basic_info', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bcourses\b', 'class', sql, flags=re.IGNORECASE)
    return sql


def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    验证 SQL 是否安全，仅允许 SELECT 查询

    返回: (是否通过, 错误信息)
    """
    sql_clean = sql.strip()
    sql_lower = sql_clean.lower()

    # 1. 必须以 SELECT 开头
    if not sql_lower.startswith('select'):
        return False, "只允许 SELECT 查询语句"

    # 2. 禁止关键字检查
    dangerous_keywords = [
        'drop', 'delete', 'truncate', 'insert', 'update', 'alter',
        'create', 'grant', 'revoke', 'show', 'describe', 'explain',
        'load_file', 'into outfile', 'dumpfile',
    ]
    for keyword in dangerous_keywords:
        if re.search(r'\b' + keyword + r'\b', sql_lower):
            return False, f"包含危险关键字: {keyword}"

    # 3. 禁止注释注入
    if '--' in sql or '/*' in sql or '*/' in sql:
        return False, "包含注释标记，可能存在注入风险"

    # 4. 禁止分号分隔的多条语句
    if sql_clean.count(';') > 1:
        return False, "不允许执行多条 SQL 语句"

    # 5. 禁止常见的注入模式
    injection_patterns = [
        r'\bor\b\s+\d+\s*=\s*\d+',
        r'\band\b\s+\d+\s*=\s*\d+',
        r'\bor\s+["\']',
        r'\band\s+["\']',
        r"union\s+select",
        r"waitfor\s+delay",
        r"benchmark\s*\(",
        r"sleep\s*\(",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, sql_lower):
            return False, "包含可疑的注入模式"

    # 6. 使用 sqlparse 进行深度解析
    try:
        parsed = sqlparse.parse(sql)[0]
        dml_found = False
        for token in parsed.flatten():
            if token.ttype in tokens.DML:
                if token.value.upper() != 'SELECT':
                    return False, f"包含非 SELECT 的 DML 操作: {token.value}"
                dml_found = True
            if token.ttype in tokens.Keyword and token.value.upper() in ['CALL', 'EXECUTE', 'EXEC']:
                return False, "不允许调用存储过程或函数"
        if not dml_found:
            return False, "未找到有效的 SELECT 语句"
    except Exception as e:
        return False, f"SQL 解析失败: {str(e)}"

    return True, None


async def similarity_search_async(vectordb: Optional[Chroma], query: str, k: int = 3) -> List[Document]:
    """异步执行向量相似度搜索"""
    def _sync():
        return vectordb.similarity_search(query, k=k)
    return await asyncio.to_thread(_sync)


async def retrieve_schema_context(vectordb: Optional[Chroma]) -> str:
    """从向量知识库检索数据库表结构上下文"""
    if vectordb is None:
        return FALLBACK_SCHEMA
    try:
        docs = await similarity_search_async(vectordb, "数据库表结构 字段定义 表名", k=2)
        if docs:
            context = "\n\n".join([doc.page_content for doc in docs])
            return context[:4000]
    except Exception as e:
        logger.error(f"检索表结构失败: {e}")
    return FALLBACK_SCHEMA


async def generate_sql(
    question: str,
    vectordb: Optional[Chroma],
    retry: bool = False,
    previous_sql: Optional[str] = None,
) -> str:
    """使用 LLM 生成 SQL 查询语句"""
    question_safe = sanitize_prompt_input(question)
    previous_sql_safe = sanitize_prompt_input(previous_sql) if previous_sql else None

    system = "你是一个MySQL专家，只输出SQL语句，不要有任何额外解释。以分号结尾。表名都是单数。"
    if retry:
        system += " 上一次生成的SQL执行失败，请修正。只输出修正后的SQL语句。"

    schema = await retrieve_schema_context(vectordb)

    if previous_sql_safe:
        user = (
            f"上一轮用户执行的SQL是：\n{previous_sql_safe}\n\n"
            f"用户现在的问题可能希望复用其中的过滤条件。\n\n"
            f"数据库结构：\n{schema}\n\n"
            f"用户问题：{question_safe}\n输出SQL："
        )
    else:
        user = f"数据库结构：\n{schema}\n\n用户问题：{question_safe}\n输出SQL："

    client = get_llm_client()
    resp = await client.chat.completions.create(
        model=get_llm_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=get_llm_temperature(),
    )
    sql = resp.choices[0].message.content.strip()
    sql = re.sub(r'^```sql\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)
    return fix_table_names(sql)


async def generate_aggregate_sql(
    question: str,
    original_desc: str,
    vectordb: Optional[Chroma],
) -> Optional[str]:
    """为数据分析需求生成聚合查询 SQL"""
    question_safe = sanitize_prompt_input(question)
    original_desc_safe = sanitize_prompt_input(original_desc)

    schema = await retrieve_schema_context(vectordb)
    prompt = AGGREGATE_SQL_PROMPT.format(
        schema=schema,
        question=question_safe,
        original_desc=original_desc_safe,
    )

    client = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
        )
        sql = resp.choices[0].message.content.strip()
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        if sql.lower().startswith("select"):
            return fix_table_names(sql)
    except Exception as e:
        logger.error(f"生成聚合SQL失败: {e}")
    return None


async def execute_sql_to_dict(db, sql: str) -> list[dict]:
    """
    执行 SQL 查询并返回字典列表
    包含 SQL 注入防护验证
    """
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise ValueError(f"SQL 验证失败: {error_msg}")

    def _sync():
        result = db.execute(text(sql))
        rows = result.fetchall()
        if not rows:
            return []
        return [dict(zip(result.keys(), row)) for row in rows]

    return await asyncio.to_thread(_sync)
