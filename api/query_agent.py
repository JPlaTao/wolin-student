import os
import re
import asyncio
import uuid
import json
import datetime as dt_module
import decimal
from enum import Enum
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import AsyncOpenAI
import sqlparse
from sqlparse import tokens

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import DashScopeEmbeddings

from core.database import get_db
from core.auth import get_current_user
from core.settings import get_settings
from model.user import User
from dao.conversation_dao import save_turn, get_recent_turns, get_turn_count, get_latest_turn, get_previous_sql_turn
from utils.logger import get_logger


# ==================== 常量定义 ====================
class QueryConstants:
    """查询相关常量"""
    MAX_HISTORY_TURNS = 5  # 历史记录轮数
    MAX_FULL_SAVE_ROWS = 100  # 全量保存的最大行数
    MAX_FULL_SAVE_JSON_SIZE = 2000  # 全量保存的最大JSON长度
    MAX_CONTEXT_CHARS = 5000  # 上下文最大字符数
    MAX_KNOWLEDGE_CHARS = 3000  # 知识库上下文最大字符数
    MAX_SAMPLE_ROWS = 10  # 样本数据行数
    LLM_MAX_TOKENS = 10  # LLM输出最大token数
    REFINE_MAX_TOKENS = 2000  # 精炼分析最大token数
    CHUNK_MIN_SIZE = 8  # 流式输出最小块大小
    CHUNK_MAX_WAIT_MS = 80  # 流式输出最大等待毫秒


# ==================== 公共函数 ====================
def _build_history_text(history_turns: List[Any], max_len: int = 200) -> str:
    """
    构建历史对话文本
    
    Args:
        history_turns: 历史记录列表
        max_len: 每个回复的最大截取长度
        
    Returns:
        格式化后的历史文本
    """
    if not history_turns:
        return ""
    history_text = ""
    for turn in history_turns:
        if turn.result_summary:
            preview = turn.result_summary[:max_len]
        else:
            preview = turn.answer_text[:max_len] if turn.answer_text else ""
        history_text += f"用户: {turn.question}\n系统: {preview}\n"
    return history_text


def _should_save_full(data: List[dict]) -> bool:
    """
    判断是否应该完整保存数据
    
    Args:
        data: 查询结果列表
        
    Returns:
        True 如果应该完整保存
    """
    if not data:
        return True
    row_count = len(data)
    json_size = len(safe_json_dumps(data))
    return (row_count <= QueryConstants.MAX_FULL_SAVE_ROWS and
            json_size <= QueryConstants.MAX_FULL_SAVE_JSON_SIZE)


def _build_ref_history_text(history_turns: List[Any]) -> str:
    """
    构建用于SQL引用检测的历史文本（最近2轮）
    
    Args:
        history_turns: 历史记录列表
        
    Returns:
        格式化后的历史文本
    """
    recent = history_turns[-2:] if len(history_turns) >= 2 else history_turns
    return "\n".join([
        f"用户: {t.question}\n系统: {t.answer_text[:100] if t.answer_text else ''}"
        for t in recent
    ])


# 获取模块专用 logger
logger = get_logger("query_agent")

router = APIRouter(prefix="/query", tags=["自然语言查询"])

settings = get_settings()


# ---------- LLM 客户端初始化 ----------
def _get_llm_api_key() -> str:
    """根据配置的 provider 获取对应的 API key"""
    provider = settings.llm.provider.lower()
    if provider == "kimi":
        return settings.api_keys.kimi
    elif provider == "deepseek":
        return settings.api_keys.deepseek
    elif provider == "openai":
        return settings.api_keys.openai
    else:
        logger.warning(f"未知的 LLM provider: {provider}，尝试使用 kimi key")
        return settings.api_keys.kimi


llm_config = settings.llm
_temperature = llm_config.effective_temperature  # 自动适配模型限制
client = AsyncOpenAI(
    api_key=_get_llm_api_key(),
    base_url=llm_config.base_url
)
logger.info(
    f"LLM 客户端初始化完成: provider={llm_config.provider}, model={llm_config.model}, base_url={llm_config.base_url}")

# ---------- 向量知识库 ----------
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


# ---------- 请求模型 ----------
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    include_history: bool = True


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


# ---------- 辅助函数 ----------
def _sanitize_prompt_input(text: str) -> str:
    """
    清洗用户输入，防止 prompt 注入攻击。
    
    攻击者可能通过在用户输入中注入指令（如"忽略上面的指令"）
    来操纵 LLM 的行为。此函数通过过滤常见的注入模式来防御此类攻击。
    
    参数:
        text: 原始用户输入
        
    返回:
        清洗后的安全文本
    """
    if not text:
        return ""

    # 移除常见的 prompt 注入指令模式
    injection_patterns = [
        # 指令类注入：忽略、disregard、forget 等
        r'(?i)(ignore\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(disregard\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(forget\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(you\s+are\s+no\s+longer)',
        r'(?i)(you\s+are\s+now\s+a)',
        r'(?i)(pretend\s+you\s+are)',
        r'(?i)(act\s+as\s+if\s+you\s+are)',
        # 角色扮演/越狱类注入
        r'(?i)(new\s+system\s+prompt)',
        r'(?i)(override\s+(your\s+)?system)',
        r'(?i)(enable\s+(developer|admin|superuser)\s+mode)',
        r'(?i)(DAN\s+mode)',
        r'(?i)(jailbreak)',
        # XML 标签类注入
        r'<system>',
        r'</system>',
        r'<system_prompt>',
        r'</system_prompt>',
        r'<instruction>',
        r'</instruction>',
        r'<\|.*?\|>',  # 通用 XML 标签
        # Markdown 代码块注入（在 user input 中可疑）
        r'```\s*(system|instruction|prompt)',
        r'```\s*ignore',
        r'```\s*disregard',
    ]

    result = text
    for pattern in injection_patterns:
        result = re.sub(pattern, '[filtered]', result, flags=re.IGNORECASE)

    return result


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

    # 1. 基础检查：必须以 SELECT 开头
    if not sql_lower.startswith('select'):
        return False, "只允许 SELECT 查询语句"

    # 2. 禁止关键字检查
    dangerous_keywords = [
        'drop', 'delete', 'truncate', 'insert', 'update', 'alter',
        'create', 'grant', 'revoke', 'show', 'describe', 'explain',
        'load_file', 'into outfile', 'dumpfile'
    ]

    for keyword in dangerous_keywords:
        # 使用单词边界匹配，避免误判（如 'updated' 包含 'update'）
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_lower):
            return False, f"包含危险关键字: {keyword}"

    # 3. 禁止注释注入
    if '--' in sql or '/*' in sql or '*/' in sql:
        return False, "包含注释标记，可能存在注入风险"

    # 4. 禁止分号分隔的多条语句
    if sql_clean.count(';') > 1:
        return False, "不允许执行多条 SQL 语句"

    # 5. 禁止常见的注入模式
    injection_patterns = [
        r'\bor\b\s+\d+\s*=\s*\d+',  # OR 1=1
        r'\band\b\s+\d+\s*=\s*\d+',  # AND 1=1
        r'\bor\s+["\']',  # OR "1"="1"
        r'\band\s+["\']',  # AND "1"="1"
        r"union\s+select",  # UNION SELECT
        r"waitfor\s+delay",  # 时间注入
        r"benchmark\s*\(",  # MySQL 盲注
        r"sleep\s*\(",  # MySQL 盲注
    ]

    for pattern in injection_patterns:
        if re.search(pattern, sql_lower):
            return False, f"包含可疑的注入模式"

    # 6. 使用 sqlparse 进行深度解析
    try:
        parsed = sqlparse.parse(sql)[0]
        dml_found = False

        for token in parsed.flatten():
            # 检查 DML 类型
            if token.ttype in tokens.DML:
                if token.value.upper() != 'SELECT':
                    return False, f"包含非 SELECT 的 DML 操作: {token.value}"
                dml_found = True

            # 检查是否包含存储过程调用
            if token.ttype in tokens.Keyword and token.value.upper() in ['CALL', 'EXECUTE', 'EXEC']:
                return False, "不允许调用存储过程或函数"

        # 如果解析成功但未找到 DML，可能是空语句或异常
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


def summarize_result(data: List[dict], max_sample_rows: int = 3, full_save: bool = False) -> str:
    """
    生成结果摘要或完整数据JSON。

    参数:
        data: 查询结果列表
        max_sample_rows: 摘要中最大样本行数
        full_save: 是否完整保存数据

    返回: JSON 格式的摘要或完整数据
    """
    if not data:
        return safe_json_dumps({"row_count": 0, "sample": []})
    if full_save:
        # 完整保存，直接序列化全部数据
        return safe_json_dumps(data, ensure_ascii=False)
    else:
        row_count = len(data)
        sample = data[:max_sample_rows]
        stats = {}
        for key in data[0].keys():
            if isinstance(data[0].get(key), (int, float)):
                values = [row.get(key) for row in data if row.get(key) is not None]
                if values:
                    stats[key] = {"avg": sum(values) / len(values), "min": min(values), "max": max(values)}
        summary = {"row_count": row_count, "sample": sample, "statistics": stats}
        return safe_json_dumps(summary, ensure_ascii=False)


# ---------- 意图分类 ----------
INTENT_CLASSIFICATION_PROMPT = """
你是一个意图分类助手。根据对话历史和当前用户问题，判断用户意图。

历史对话（最近5轮）：
{history}

当前问题：{question}

意图选项（只输出一个单词）：
- sql: 用户需要从数据库查询具体数据（如"查询成绩"、"统计人数"、"列出学生"）
- analysis: 用户希望进行数据分析、解释原因、对比趋势（如"为什么成绩低"、"分析就业率变化"）
- chat: 其他日常闲聊、问候、无关问题

意图：
"""


async def classify_intent_llm(question: str, history_text: str = "") -> str:
    """使用 LLM 进行意图分类"""
    # 清洗用户输入，防止 prompt 注入
    question_safe = _sanitize_prompt_input(question)
    history_safe = _sanitize_prompt_input(history_text)

    if history_safe:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(history=history_safe, question=question_safe)
    else:
        prompt = f"意图选项：sql / analysis / chat\n用户问题：{question_safe}\n意图："
    try:
        resp = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=_temperature,
            max_tokens=10
        )
        intent = resp.choices[0].message.content.strip().lower()
        if intent in ["sql", "analysis", "chat"]:
            return intent
    except Exception as e:
        logger.warning(f"LLM意图分类失败: {e}，降级到关键词匹配")
    # 降级关键词
    knowledge_keywords = ["为什么", "什么原因", "解释", "说明", "含义", "规则", "定义", "分析", "分布", "趋势", "对比"]
    if any(kw in question for kw in knowledge_keywords):
        return "analysis"
    sql_keywords = ["查询", "多少", "几个", "平均", "最高", "最低", "排名", "列表", "统计", "每个", "各个", "薪资",
                    "年龄", "成绩", "学生", "班级", "老师", "就业", "考试"]
    if any(kw in question for kw in sql_keywords):
        return "sql"
    return "chat"


# ---------- SQL 历史引用检测 ----------
SQL_REFERENCE_CHECK_PROMPT = """
你是一个判断助手。根据对话历史和当前问题，判断用户是否想要**基于上一轮查询结果**进行新的查询。
上一轮查询可能提供了一些过滤条件（如班级名称、时间范围等），用户可能希望复用这些条件。

对话历史（最近2轮）：
{history}

当前问题：{question}

判断规则：
- 如果用户明确提到"刚才"、"上一轮"、"再查一下"、"同样的"、"也"、"那个"、"再次"、"同样"等词，或者明显引用上一轮的结果（如"那个班的就业率"），返回 "YES"。
- 否则返回 "NO"。

只输出 YES 或 NO。
"""


async def check_sql_reference(question: str, history_text: str) -> str:
    """检测用户是否需要引用上一轮的 SQL 查询"""
    # 清洗用户输入，防止 prompt 注入
    question_safe = _sanitize_prompt_input(question)
    history_safe = _sanitize_prompt_input(history_text)
    prompt = SQL_REFERENCE_CHECK_PROMPT.format(history=history_safe, question=question_safe)
    try:
        resp = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=_temperature,
            max_tokens=10
        )
        result = resp.choices[0].message.content.strip().upper()
        if result in ["YES", "NO"]:
            return result
    except Exception as e:
        logger.error(f"SQL引用检测失败: {e}")
    # 降级关键词
    reference_keywords = ["刚才", "上一轮", "再查", "同样的", "也", "那个", "再次", "同样", "这个班", "那个班"]
    if any(kw in question for kw in reference_keywords):
        return "YES"
    return "NO"


# ---------- SQL 生成 ----------
async def generate_sql(question: str, vectordb: Optional[Chroma], retry: bool = False,
                       previous_sql: Optional[str] = None) -> str:
    """使用 LLM 生成 SQL 查询语句"""
    # 清洗用户输入，防止 prompt 注入
    question_safe = _sanitize_prompt_input(question)
    previous_sql_safe = _sanitize_prompt_input(previous_sql) if previous_sql else None

    system = "你是一个MySQL专家，只输出SQL语句，不要有任何额外解释。以分号结尾。表名都是单数。"
    if retry:
        system += " 上一次生成的SQL执行失败，请修正。只输出修正后的SQL语句。"
    schema = await retrieve_schema_context(vectordb)
    user = f"数据库结构：\n{schema}\n\n用户问题：{question_safe}\n输出SQL："
    if previous_sql_safe:
        user = f"上一轮用户执行的SQL是：\n{previous_sql_safe}\n\n用户现在的问题可能希望复用其中的过滤条件。\n\n数据库结构：\n{schema}\n\n用户问题：{question_safe}\n输出SQL："
    resp = await client.chat.completions.create(
        model=llm_config.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=_temperature,
    )
    sql = resp.choices[0].message.content.strip()
    sql = re.sub(r'^```sql\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)
    return fix_table_names(sql)


class SafeJSONEncoder(json.JSONEncoder):
    """
    安全的 JSON 编码器，自动处理所有不可序列化的类型。
    使用方式: json.dumps(data, cls=SafeJSONEncoder)
    """

    def default(self, obj):
        # datetime 类型
        if isinstance(obj, (dt_module.datetime, dt_module.date, dt_module.time)):
            return obj.isoformat()
        # Decimal 类型
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        # UUID 类型
        if isinstance(obj, uuid.UUID):
            return str(obj)
        # bytes 类型
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except:
                return obj.hex()
        # Enum 类型
        if isinstance(obj, Enum):
            return obj.value
        # set/frozenset 转为列表
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        # 其他有 __dict__ 的对象
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        # 最后尝试 str()
        try:
            return str(obj)
        except:
            return f"<unserializable: {type(obj).__name__}>"


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """
    安全的 JSON 序列化函数，自动处理不可序列化类型。
    用法与 json.dumps 完全相同，只需替换函数名即可。
    """
    return json.dumps(obj, cls=SafeJSONEncoder, **kwargs)


async def execute_sql_to_dict(db: Session, sql: str) -> List[dict]:
    """
    执行 SQL 查询并返回字典列表

    包含 SQL 注入防护验证
    返回的数据已转换为 JSON 安全类型
    """
    # SQL 安全验证
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"SQL 验证失败: {error_msg}")

    def _sync():
        result = db.execute(text(sql))
        rows = result.fetchall()
        if not rows:
            return []
        # 列名和行数据组合为字典
        return [dict(zip(result.keys(), row)) for row in rows]

    return await asyncio.to_thread(_sync)


# ---------- 聚合 SQL 生成 ----------
AGGREGATE_SQL_PROMPT = """
你是一个SQL专家。根据以下表结构，为数据分析需求生成一条聚合查询。

要求：
- 只输出SELECT语句，使用聚合函数（COUNT, AVG, SUM, GROUP BY等）
- 返回行数不超过20行
- 必须过滤 is_deleted = 0
- 如果原始查询涉及特定范围，请在WHERE中体现

表结构：
{schema}

用户分析需求：{question}
原始查询描述（若有）：{original_desc}

输出SQL：
"""


async def generate_aggregate_sql(question: str, original_desc: str, vectordb: Optional[Chroma]) -> Optional[str]:
    """为数据分析需求生成聚合查询 SQL"""
    # 清洗用户输入，防止 prompt 注入
    question_safe = _sanitize_prompt_input(question)
    original_desc_safe = _sanitize_prompt_input(original_desc)

    schema = await retrieve_schema_context(vectordb)
    prompt = AGGREGATE_SQL_PROMPT.format(schema=schema, question=question_safe, original_desc=original_desc_safe)
    try:
        resp = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=_temperature,
        )
        sql = resp.choices[0].message.content.strip()
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        if sql.lower().startswith("select"):
            return fix_table_names(sql)
    except Exception as e:
        logger.error(f"生成聚合SQL失败: {e}")
    return None


# ---------- 数据分析精炼 ----------
ANALYSIS_REFINE_PROMPT = """
你是一个数据分析专家，请对以下初步分析结果进行精简和规范化。

要求：
- 删除重复的句子或观点
- 合并相似结论
- 去掉无意义的填充词（如"总的来说"、"首先呢"、"那么"等）
- 保留关键数据、原因、建议
- 输出结构：结论 → 数据支撑 → 可能原因 → 建议

原始分析结果：
{raw_analysis}

请输出精炼后的最终回答：
"""


async def refine_analysis(raw_analysis: str) -> str:
    """对原始分析结果进行精简和规范化"""
    prompt = ANALYSIS_REFINE_PROMPT.format(raw_analysis=raw_analysis)
    try:
        resp = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=_temperature,
        )
        refined = resp.choices[0].message.content.strip()
        return refined
    except Exception as e:
        logger.warning(f"精炼分析失败: {e}，返回原始结果")
        return raw_analysis


# ---------- SQL 执行与保存结果 ----------
def _build_sql_result_response(sql: str, data: List[dict], session_id: str, turn_index: int,
                               row_count: int, full_save: bool) -> dict:
    """
    构建 SQL 查询结果的响应字典

    Args:
        sql: 执行的 SQL 语句
        data: 查询结果数据
        session_id: 会话ID
        turn_index: 轮次索引
        row_count: 结果行数
        full_save: 是否全量保存

    Returns:
        响应字典
    """
    if full_save:
        return {
            "type": "sql",
            "session_id": session_id,
            "turn_index": turn_index,
            "sql": sql,
            "data": data,
            "count": row_count,
            "full_data_saved": True
        }
    else:
        sample_data = data[:QueryConstants.MAX_SAMPLE_ROWS]
        message = f"数据量较大（共{row_count}行），已为您存储分析标记。您可以继续提问'分析这些数据'。"
        return {
            "type": "sql",
            "session_id": session_id,
            "turn_index": turn_index,
            "sql": sql,
            "data_truncated": True,
            "sample_data": sample_data,
            "message": message,
            "full_data_saved": False
        }


def _build_sql_result_summary(data: List[dict], row_count: int, full_save: bool) -> tuple[str, str]:
    """
    构建 SQL 结果摘要和回答文本

    Args:
        data: 查询结果数据
        row_count: 结果行数
        full_save: 是否全量保存

    Returns:
        (result_summary, answer_text)
    """
    result_summary = summarize_result(data, full_save=full_save)
    if full_save:
        answer_text = f"查询成功，共{row_count}条记录。"
    else:
        answer_text = f"数据量较大（共{row_count}行），已为您存储分析标记。您可以继续提问'分析这些数据'。"
    return result_summary, answer_text


async def _execute_and_save_sql(db: Session, sql: str, user_id: int, session_id: str,
                                turn_index: int, question: str,
                                is_retry: bool = False) -> tuple[List[dict], str, bool]:
    """
    执行 SQL 并保存结果，返回 (data, answer_text, full_save)

    Args:
        db: 数据库会话
        sql: SQL 语句
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        question: 用户问题
        is_retry: 是否为重试执行

    Returns:
        (查询数据, 回答文本, 是否全量保存)
    """
    data = await execute_sql_to_dict(db, sql)
    row_count = len(data)
    full_save = _should_save_full(data)
    result_summary, answer_text = _build_sql_result_summary(data, row_count, full_save)

    sql_label = "（已修正）" if is_retry else ""
    answer_text = f"查询成功，共{row_count}条记录{sql_label}。"

    save_turn(db, user_id, session_id, turn_index, question,
              sql_query=sql, result_summary=result_summary,
              answer_text=answer_text, full_data_saved=full_save)

    logger.info(f"会话 {session_id} SQL执行{'成功' if not is_retry else '重试成功'}，返回 {row_count} 条记录")
    return data, answer_text, full_save


# ---------- 历史 SQL 引用检测 ----------
async def _get_previous_sql_reference(db: Session, user_id: int, session_id: str,
                                      history_turns: List[Any], question: str) -> tuple[bool, Optional[str]]:
    """
    检查是否需要引用上一轮的 SQL 查询

    Args:
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        history_turns: 历史记录列表
        question: 当前问题

    Returns:
        (是否需要引用, 上一轮SQL语句)
    """
    if not history_turns:
        return False, None

    previous_sql_turn = get_previous_sql_turn(db, user_id, session_id)
    if not previous_sql_turn or not previous_sql_turn.sql_query:
        return False, None

    ref_history = _build_ref_history_text(history_turns)
    reference_check = await check_sql_reference(question, ref_history)
    need_reference = (reference_check == "YES")

    logger.info(f"会话 {session_id} SQL引用检测结果: {reference_check}")
    return need_reference, previous_sql_turn.sql_query if need_reference else None


# ---------- 数据分析处理 ----------
async def _build_analysis_context(db: Session, user_id: int, session_id: str, question: str,
                                  include_history: bool, vectordb: Optional[Chroma],
                                  limit: int = 5) -> tuple[str, str, Optional[str]]:
    """
    构建数据分析所需的上下文信息

    Args:
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        question: 当前问题
        include_history: 是否包含历史
        vectordb: 向量知识库
        limit: 历史记录限制

    Returns:
        (data_context, knowledge_context, aggregate_sql_used)
    """
    data_context = ""
    knowledge_context = ""
    aggregate_sql_used = None

    latest_turn = get_latest_turn(db, user_id, session_id)
    if latest_turn and latest_turn.result_summary:
        try:
            if latest_turn.full_data_saved:
                full_data = json.loads(latest_turn.result_summary)
                data_context = f"上一轮查询得到的完整数据（共{len(full_data)}条）：\n{safe_json_dumps(full_data, indent=2)[:QueryConstants.MAX_CONTEXT_CHARS]}\n"
            else:
                original_desc = latest_turn.question
                aggregate_sql = await generate_aggregate_sql(question, original_desc, vectordb)
                if aggregate_sql:
                    agg_data = await execute_sql_to_dict(db, aggregate_sql)
                    agg_summary = summarize_result(agg_data, full_save=False)
                    data_context = f"根据您的分析需求，自动生成的聚合数据：\n{agg_summary}\n"
                    aggregate_sql_used = aggregate_sql
                else:
                    data_context = "上一轮查询数据量较大，无法直接分析，且自动生成聚合SQL失败。请提出更具体的统计需求（例如：按分数段统计人数）。\n"
        except Exception as e:
            data_context = f"读取上一轮数据失败：{str(e)}\n"
    else:
        data_context = "未找到上一轮的数据。请先执行一次SQL查询，再进行分析。\n"

    if vectordb:
        docs = await similarity_search_async(vectordb, question, k=3)
        if docs:
            knowledge_context = "\n\n".join([doc.page_content for doc in docs])[:QueryConstants.MAX_KNOWLEDGE_CHARS]

    return data_context, knowledge_context, aggregate_sql_used


async def _process_analysis_branch(db: Session, user_id: int, session_id: str,
                                   turn_index: int, question: str,
                                   include_history: bool, vectordb: Optional[Chroma]) -> tuple[str, Optional[str], str]:
    """
    处理数据分析意图

    Args:
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        question: 用户问题
        include_history: 是否包含历史
        vectordb: 向量知识库

    Returns:
        (answer, aggregate_sql_used, raw_answer)
    """
    analysis_history = get_recent_turns(db, user_id, session_id, limit=5) if include_history else []
    data_context, knowledge_context, aggregate_sql_used = await _build_analysis_context(
        db, user_id, session_id, question, include_history, vectordb)

    hist_text = "\n".join([
        f"用户: {turn.question}\n系统: {turn.answer_text[:200] if turn.answer_text else ''}"
        for turn in analysis_history
    ])

    question_safe = _sanitize_prompt_input(question)
    data_context_safe = _sanitize_prompt_input(data_context)
    knowledge_context_safe = _sanitize_prompt_input(knowledge_context)
    hist_text_safe = _sanitize_prompt_input(hist_text)

    analysis_prompt = f"""你是一个数据分析专家。请**严格基于以下提供的数据**回答用户的分析问题。不要编造数据。

【提供的数据】
{data_context_safe}

【参考分析指南】
{knowledge_context_safe}

【历史对话记录（仅供参考）】
{hist_text_safe}

【用户问题】
{question_safe}

请给出清晰的分析结论、可能的原因和建议。如果数据不足，请明确指出缺少哪些数据，而不是给出通用回答。"""

    try:
        resp_raw = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=_temperature,
        )
        raw_answer = resp_raw.choices[0].message.content
        refined_answer = await refine_analysis(raw_answer)
        answer = refined_answer

        save_turn(db, user_id, session_id, turn_index, question, answer_text=answer,
                  aggregate_sql=aggregate_sql_used, full_data_saved=False)
        logger.info(f"会话 {session_id} 数据分析完成")
        return answer, aggregate_sql_used, raw_answer
    except Exception as e:
        logger.error(f"会话 {session_id} 分析失败: {e}")
        raise HTTPException(500, f"分析失败: {str(e)}")


# ---------- 闲聊处理 ----------
async def _process_chat_branch(db: Session, user_id: int, session_id: str,
                               turn_index: int, question: str, include_history: bool) -> str:
    """
    处理闲聊意图

    Args:
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        question: 用户问题
        include_history: 是否包含历史

    Returns:
        回答文本
    """
    chat_history = get_recent_turns(db, user_id, session_id, limit=5) if include_history else []
    chat_history_text = "\n".join([
        f"用户: {turn.question}\n助手: {turn.answer_text}"
        for turn in chat_history
    ])

    question_safe = _sanitize_prompt_input(question)
    chat_history_safe = _sanitize_prompt_input(chat_history_text)

    if chat_history_safe:
        chat_prompt = f"以下是用户与助手的对话历史。请根据历史回答用户的问题。如果历史中有相关信息，请引用。\n\n{chat_history_safe}\n\n用户最新问题：{question_safe}\n助手："
    else:
        chat_prompt = f"用户：{question_safe}\n助手："

    try:
        resp = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": chat_prompt}],
            temperature=_temperature,
        )
        answer = resp.choices[0].message.content
        save_turn(db, user_id, session_id, turn_index, question, answer_text=answer)
        logger.info(f"会话 {session_id} 闲聊回复完成")
        return answer
    except Exception as e:
        logger.error(f"会话 {session_id} 闲聊失败: {e}")
        raise HTTPException(500, f"闲聊失败: {str(e)}")


# ---------- 主接口 ----------
@router.post("/natural")
async def natural_query(req: QueryRequest, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """
    自然语言查询主接口

    支持三种意图：
    - sql: SQL 查询
    - analysis: 数据分析
    - chat: 闲聊
    """
    question = req.question
    user_id = current_user.id  # 从认证用户获取 user_id
    session_id = req.session_id

    logger.info(f"收到请求 - question: {question[:50]}..., session_id: {session_id}, user_id: {user_id}")

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"未提供 session_id，已生成新会话: {session_id}，user_id: {user_id}")

    include_history = req.include_history

    # 获取历史记忆（用于意图分类和闲聊/分析）
    history_turns = get_recent_turns(db, user_id, session_id,
                                     limit=QueryConstants.MAX_HISTORY_TURNS) if include_history else []
    logger.info(f"会话 {session_id} (user_id={user_id}) 历史记录数: {len(history_turns)}")

    history_text = _build_history_text(history_turns)

    # 意图分类
    intent = await classify_intent_llm(question, history_text)
    logger.info(f"会话 {session_id} 意图分类结果: {intent}")

    turn_index = get_turn_count(db, user_id, session_id) + 1

    # ---------- SQL 分支 ----------
    if intent == "sql":
        need_reference, previous_sql = await _get_previous_sql_reference(
            db, user_id, session_id, history_turns, question)

        try:
            sql = await generate_sql(question, vectordb, retry=False, previous_sql=previous_sql)
            logger.debug(f"会话 {session_id} 生成的SQL: {sql}")
        except Exception as e:
            logger.error(f"会话 {session_id} 生成SQL失败: {e}")
            raise HTTPException(500, f"生成SQL失败: {e}")

        if not sql.strip().lower().startswith("select"):
            logger.warning(f"会话 {session_id} 生成的非SELECT语句: {sql}")
            raise HTTPException(400, "只能生成SELECT语句")

        try:
            data, answer_text, full_save = await _execute_and_save_sql(
                db, sql, user_id, session_id, turn_index, question)
            row_count = len(data)
            return _build_sql_result_response(sql, data, session_id, turn_index, row_count, full_save)
        except Exception as e:
            logger.warning(f"会话 {session_id} SQL执行失败，准备重试: {e}")
            try:
                sql_corrected = await generate_sql(question, vectordb, retry=True, previous_sql=previous_sql)
                data2, answer_text2, full_save2 = await _execute_and_save_sql(
                    db, sql_corrected, user_id, session_id, turn_index, question, is_retry=True)
                row_count2 = len(data2)
                return _build_sql_result_response(sql_corrected, data2, session_id, turn_index, row_count2, full_save2)
            except Exception as e2:
                logger.error(f"会话 {session_id} SQL重试失败: 原始错误={e}, 修正错误={e2}")
                raise HTTPException(500, f"SQL执行失败: {str(e)}\n原始SQL: {sql}\n修正SQL: {sql_corrected}")

    # ---------- 数据分析分支 ----------
    elif intent == "analysis":
        logger.info(f"会话 {session_id} 进入数据分析分支")
        answer, aggregate_sql_used, raw_answer = await _process_analysis_branch(
            db, user_id, session_id, turn_index, question, include_history, vectordb)
        return {
            "type": "answer",
            "session_id": session_id,
            "turn_index": turn_index,
            "answer": answer,
            "raw_analysis": raw_answer
        }

    # ---------- 闲聊分支 ----------
    else:
        logger.info(f"会话 {session_id} 进入闲聊分支")
        answer = await _process_chat_branch(
            db, user_id, session_id, turn_index, question, include_history)
        return {
            "type": "answer",
            "session_id": session_id,
            "turn_index": turn_index,
            "answer": answer
        }


# ========== 流式输出支持 ==========

class StreamBuffer:
    """流式输出缓冲区管理器"""

    def __init__(self, min_chunk_size: int = 5, max_wait_ms: int = 50):
        """
        参数:
            min_chunk_size: 最小累积字符数才发送一次
            max_wait_ms: 最大等待毫秒数，即使未达到最小字符数也发送
        """
        self.min_chunk_size = min_chunk_size
        self.max_wait_ms = max_wait_ms
        self.buffer = ""
        self.last_send_time = dt_module.datetime.now()

    def add(self, text: str) -> list[str]:
        """添加文本，返回可发送的 chunks"""
        self.buffer += text
        chunks = []
        now = dt_module.datetime.now()
        elapsed = (now - self.last_send_time).total_seconds() * 1000

        # 如果缓冲区超过最小大小或等待时间超时
        if len(self.buffer) >= self.min_chunk_size or elapsed >= self.max_wait_ms:
            if self.buffer:
                chunks.append(self.buffer)
                self.buffer = ""
                self.last_send_time = now

        return chunks

    def flush(self) -> str:
        """强制刷新缓冲区，返回剩余内容"""
        result = self.buffer
        self.buffer = ""
        self.last_send_time = dt_module.datetime.now()
        return result


# ---------- 流式 SQL 处理 ----------
async def _stream_sql_processing(question: str, db: Session, user_id: int, session_id: str,
                                 turn_index: int, vectordb: Optional[Chroma],
                                 buffer: StreamBuffer, temperature: float):
    """
    流式处理 SQL 查询意图

    Args:
        question: 用户问题
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        vectordb: 向量知识库
        buffer: 流式缓冲区
        temperature: LLM 温度参数
    """
    yield {"event": "thinking", "data": "正在生成SQL查询..."}

    need_reference, previous_sql = False, None
    try:
        need_reference, previous_sql = await _get_previous_sql_reference(
            db, user_id, session_id, [], question)
    except Exception:
        pass

    sql = await generate_sql(question, vectordb, retry=False, previous_sql=previous_sql)
    sql = sql.strip()

    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        yield {"event": "error", "data": f"SQL验证失败: {error_msg}"}
        yield {"event": "done", "data": ""}
        return

    yield {"event": "sql", "data": sql}
    yield {"event": "thinking", "data": "正在执行查询..."}

    try:
        data = await execute_sql_to_dict(db, sql)
        row_count = len(data)
        full_save = _should_save_full(data)
        result_summary, answer_text = _build_sql_result_summary(data, row_count, full_save)

        yield {"event": "data", "data": {
            "row_count": row_count,
            "full_save": full_save,
            "data": data if full_save else data[:QueryConstants.MAX_SAMPLE_ROWS],
            "message": answer_text
        }}

        save_turn(db, user_id, session_id, turn_index, question,
                  sql_query=sql, result_summary=result_summary,
                  answer_text=answer_text, full_data_saved=full_save)

        yield {"event": "thinking", "data": "正在生成回答..."}
        answer_prompt = f"请基于以下SQL查询结果，用自然语言回答用户问题。\n\nSQL: {sql}\n结果: {answer_text}\n\n用户问题: {question}\n\n回答:"
        async for chunk in stream_llm_chunk(answer_prompt, buffer, temperature):
            yield chunk

    except Exception as e:
        logger.warning(f"会话 {session_id} SQL执行失败，尝试重试: {e}")
        yield {"event": "thinking", "data": "SQL执行失败，正在修正..."}

        try:
            sql_corrected = await generate_sql(question, vectordb, retry=True, previous_sql=previous_sql)
            yield {"event": "sql", "data": sql_corrected}

            data = await execute_sql_to_dict(db, sql_corrected)
            row_count = len(data)
            full_save = _should_save_full(data)
            result_summary, answer_text = _build_sql_result_summary(data, row_count, full_save)
            answer_text = f"查询成功，共{row_count}条记录（已修正）。"

            yield {"event": "data", "data": {
                "row_count": row_count,
                "full_save": full_save,
                "data": data if full_save else data[:QueryConstants.MAX_SAMPLE_ROWS],
                "message": answer_text
            }}

            save_turn(db, user_id, session_id, turn_index, question,
                      sql_query=sql_corrected, result_summary=result_summary,
                      answer_text=answer_text, full_data_saved=full_save)

            answer_prompt = f"请基于修正后的SQL查询结果回答用户。\n\nSQL: {sql_corrected}\n结果: {answer_text}\n\n用户问题: {question}"
            async for chunk in stream_llm_chunk(answer_prompt, buffer, temperature):
                yield chunk

        except Exception as e2:
            yield {"event": "error", "data": f"SQL执行失败: {str(e2)}"}
            yield {"event": "done", "data": ""}


# ---------- 流式分析处理 ----------
async def _stream_analysis_processing(question: str, db: Session, user_id: int, session_id: str,
                                      turn_index: int, vectordb: Optional[Chroma],
                                      buffer: StreamBuffer, temperature: float):
    """
    流式处理数据分析意图

    Args:
        question: 用户问题
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        vectordb: 向量知识库
        buffer: 流式缓冲区
        temperature: LLM 温度参数
    """
    yield {"event": "thinking", "data": "正在分析数据..."}

    data_context, knowledge_context, aggregate_sql_used = await _build_analysis_context(
        db, user_id, session_id, question, True, vectordb)

    question_safe = _sanitize_prompt_input(question)
    data_context_safe = _sanitize_prompt_input(data_context)
    knowledge_context_safe = _sanitize_prompt_input(knowledge_context)

    analysis_prompt = f"""你是一个数据分析专家。请严格基于以下提供的数据回答用户的分析问题。不要编造数据。

【提供的数据】
{data_context_safe}

【参考分析指南】
{knowledge_context_safe}

【用户问题】
{question_safe}

请给出清晰的分析结论、可能的原因和建议。"""

    async for chunk in stream_llm_chunk(analysis_prompt, buffer, temperature):
        yield chunk

    final_answer = buffer.flush()
    save_turn(db, user_id, session_id, turn_index, question,
              answer_text=final_answer, aggregate_sql=aggregate_sql_used,
              full_data_saved=False)


# ---------- 流式闲聊处理 ----------
async def _stream_chat_processing(question: str, db: Session, user_id: int, session_id: str,
                                  turn_index: int, buffer: StreamBuffer, temperature: float):
    """
    流式处理闲聊意图

    Args:
        question: 用户问题
        db: 数据库会话
        user_id: 用户ID
        session_id: 会话ID
        turn_index: 轮次索引
        buffer: 流式缓冲区
        temperature: LLM 温度参数
    """
    yield {"event": "thinking", "data": "正在思考..."}

    chat_history = get_recent_turns(db, user_id, session_id, limit=5)
    chat_history_text = "\n".join([
        f"用户: {turn.question}\n助手: {turn.answer_text}"
        for turn in chat_history
    ])

    question_safe = _sanitize_prompt_input(question)
    chat_history_safe = _sanitize_prompt_input(chat_history_text)

    if chat_history_safe:
        chat_prompt = f"以下是用户与助手的对话历史。请根据历史回答用户的问题。\n\n{chat_history_safe}\n\n用户最新问题：{question_safe}\n助手："
    else:
        chat_prompt = f"用户：{question_safe}\n助手："

    async for chunk in stream_llm_chunk(chat_prompt, buffer, temperature):
        yield chunk

    final_answer = buffer.flush()
    save_turn(db, user_id, session_id, turn_index, question, answer_text=final_answer)


# ---------- 流式主函数 ----------
async def stream_llm_response(question: str, history_text: str, intent: str,
                              user_id: int, session_id: str, turn_index: int,
                              db: Session, vectordb: Optional[Chroma]) -> dict:
    """
    流式处理问答，返回生成器

    返回的事件类型:
    - type: "intent" - 意图分类结果
    - type: "thinking" - 思考中状态
    - type: "sql" - 生成的SQL
    - type: "data" - 查询结果
    - type: "chunk" - 回答内容片段
    - type: "done" - 完成
    - type: "error" - 错误
    """
    buffer = StreamBuffer(min_chunk_size=8, max_wait_ms=80)
    temp = _temperature  # 使用配置的温度（自动适配模型限制）

    try:
        # 1. 发送意图分类
        logger.info(f"会话 {session_id} 流式处理 - 意图: {intent}")
        yield {"event": "intent", "data": intent}

        # 2. 根据意图分支处理
        if intent == "sql":
            async for event in _stream_sql_processing(
                    question, db, user_id, session_id, turn_index, vectordb, buffer, temp):
                yield event
        elif intent == "analysis":
            async for event in _stream_analysis_processing(
                    question, db, user_id, session_id, turn_index, vectordb, buffer, temp):
                yield event
        else:  # chat
            async for event in _stream_chat_processing(
                    question, db, user_id, session_id, turn_index, buffer, temp):
                yield event

        yield {"event": "done", "data": ""}

    except Exception as e:
        logger.error(f"会话 {session_id} 流式处理异常: {e}")
        yield {"event": "error", "data": f"处理异常: {str(e)}"}
        yield {"event": "done", "data": ""}


async def stream_llm_chunk(prompt: str, buffer: StreamBuffer, temperature: float = None) -> dict:
    """流式调用 LLM 并返回 chunks"""
    if temperature is None:
        temperature = _temperature
    try:
        stream = await client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                # 累积到缓冲区
                chunks = buffer.add(content)
                for c in chunks:
                    yield {"event": "chunk", "data": c}

        # 刷新剩余内容
        remaining = buffer.flush()
        if remaining:
            yield {"event": "chunk", "data": remaining}

    except Exception as e:
        logger.error(f"LLM流式调用失败: {e}")
        raise


# ========== 流式输出接口 ==========

@router.post("/stream")
async def stream_natural_query(req: QueryRequest, db: Session = Depends(get_db),
                               current_user: User = Depends(get_current_user)):
    """
    流式自然语言查询接口

    使用 SSE (Server-Sent Events) 实现流式输出
    """
    question = req.question
    user_id = current_user.id
    session_id = req.session_id
    include_history = req.include_history

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"未提供 session_id，已生成新会话: {session_id}")

    logger.info(f"流式请求 - 会话 {session_id}, 问题: {question[:50]}...")

    # 获取历史
    history_turns = get_recent_turns(db, user_id, session_id, limit=5) if include_history else []
    history_text = ""
    for turn in history_turns:
        preview = turn.result_summary[:200] if turn.result_summary else (
            turn.answer_text[:200] if turn.answer_text else "")
        history_text += f"用户: {turn.question}\n系统: {preview}\n"

    # 意图分类
    intent = await classify_intent_llm(question, history_text)
    turn_index = get_turn_count(db, user_id, session_id) + 1

    async def event_generator():
        """SSE 事件生成器"""
        try:
            async for event in stream_llm_response(question, history_text, intent,
                                                   user_id, session_id, turn_index, db, vectordb):
                # 格式化 SSE 事件
                event_type = event.get("event", "message")
                event_data = event.get("data", "")

                if isinstance(event_data, dict):
                    event_data = safe_json_dumps(event_data)

                # 添加延迟，控制输出速度（避免过快导致界面卡顿）
                await asyncio.sleep(0.02)

                yield f"event: {event_type}\ndata: {event_data}\n\n"

        except Exception as e:
            logger.error(f"SSE生成器异常: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )
