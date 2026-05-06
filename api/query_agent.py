import os
import asyncio
import uuid
from typing import Optional, List, Any
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from core.database import get_db
from core.auth import get_current_user
from core.settings import get_settings
from core.exceptions import BusinessException, ValidationException
from model.user import User
from dao.conversation_dao import save_turn, get_recent_turns, get_turn_count, get_latest_turn, get_previous_sql_turn
from utils.logger import get_logger
from utils.json_encoder import safe_json_dumps
from services.stream_buffer import StreamBuffer
from services.llm_service import get_llm_client, get_llm_temperature
from services.query_agent_service import agent_sql_query
from services.intent_classifier import classify_intent_llm, check_sql_reference, sanitize_prompt_input
from services.sql_generator import generate_sql, validate_sql, execute_sql_to_dict, retrieve_schema_context
from services.analysis_service import summarize_result, refine_analysis, build_analysis_context, process_analysis_branch, process_chat_branch


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


# ---------- Prompt 模板加载 ----------
from prompts.loader import load_prompt as _load_prompt


# ---------- LLM 客户端（延迟初始化，首次使用时触发）----------
class _LazyClient:
    """首次访问属性时触发 LLM 客户端初始化"""
    def __getattr__(self, name):
        return getattr(get_llm_client(), name)


client = _LazyClient()
_temperature = get_llm_temperature()

# llm_config 仅在 model 属性上被使用，保持引用以最小化改动
llm_config = settings.llm

# ---------- 向量知识库 ----------
vectordb = None
try:
    api_key = settings.api_keys.dashscope
    if not api_key:
        logger.warning("[QueryAgent] 未配置 DASHSCOPE_API_KEY，知识库功能不可用")
    else:
        embeddings = DashScopeEmbeddings(model="text-embedding-v4", dashscope_api_key=api_key)
        if os.path.exists("./chroma_db") and os.path.isdir("./chroma_db"):
            vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            logger.info("[QueryAgent] 向量知识库加载成功")
        else:
            logger.warning("[QueryAgent] 知识库目录不存在，请先运行 build_knowledge_base() 构建")
except Exception as e:
    logger.error(f"[QueryAgent] 向量知识库加载失败: {e}")


# ---------- 请求模型 ----------
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    include_history: bool = True
    use_agent: Optional[bool] = None  # None=使用 config 默认, true/false=强制切换






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

    logger.info(f"[{session_id[:8]}] [QueryAgent] SQL执行{'成功' if not is_retry else '重试成功'}，返回 {row_count} 条记录")
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

    logger.info(f"[{session_id[:8]}] [QueryAgent] SQL引用检测结果: {reference_check}")
    return need_reference, previous_sql_turn.sql_query if need_reference else None






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

    logger.info(f"[{session_id[:8]}] [QueryAgent] 请求: question={question[:50]}..., user_id={user_id}")

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"[{session_id[:8]}] [QueryAgent] 新会话, user_id={user_id}")

    include_history = req.include_history

    # 获取历史记忆（用于意图分类和闲聊/分析）
    history_turns = get_recent_turns(db, user_id, session_id,
                                     limit=QueryConstants.MAX_HISTORY_TURNS) if include_history else []
    logger.info(f"[{session_id[:8]}] [QueryAgent] (user_id={user_id}) 历史记录数: {len(history_turns)}")

    history_text = _build_history_text(history_turns)

    # 意图分类
    intent = await classify_intent_llm(question, history_text)
    logger.info(f"[{session_id[:8]}] [QueryAgent] 意图分类结果: {intent}")

    turn_index = get_turn_count(db, user_id, session_id) + 1

    # ---------- SQL 分支 ----------
    if intent == "sql":
        # ---- LangChain Agent 路径（通过 config.json 或请求参数切换）----
        use_agent = req.use_agent if req.use_agent is not None else getattr(settings.llm, 'use_agent', False)

        if use_agent:
            logger.info(f"[{session_id[:8]}] [QueryAgent] 使用 LangChain Agent 路径")
            result = await agent_sql_query(question, session_id, db)
            sql = result["sql"]
            data = result["data"]
            count = result["count"]

            if not sql:
                logger.error(f"[{session_id[:8]}] [QueryAgent] Agent 未能生成 SQL 查询")
                raise BusinessException(message="Agent 未能生成有效的 SQL 查询")

            full_save = _should_save_full(data)
            result_summary, answer_text = _build_sql_result_summary(data, count, full_save)
            save_turn(db, user_id, session_id, turn_index, question,
                      sql_query=sql, result_summary=result_summary,
                      answer_text=answer_text, full_data_saved=full_save)
            return _build_sql_result_response(sql, data, session_id, turn_index, count, full_save)

        # ---- 原有手写路径（兜底）----
        need_reference, previous_sql = await _get_previous_sql_reference(
            db, user_id, session_id, history_turns, question)

        try:
            sql = await generate_sql(question, vectordb, retry=False, previous_sql=previous_sql)
            logger.debug(f"[{session_id[:8]}] [QueryAgent] 生成的SQL: {sql}")
        except Exception as e:
            logger.error(f"[{session_id[:8]}] [QueryAgent] 生成SQL失败: {e}")
            raise BusinessException(message=f"生成SQL失败: {e}")

        if not sql.strip().lower().startswith("select"):
            logger.warning(f"[{session_id[:8]}] [QueryAgent] 生成的非SELECT语句: {sql}")
            raise ValidationException(message="只能生成SELECT语句")

        try:
            data, answer_text, full_save = await _execute_and_save_sql(
                db, sql, user_id, session_id, turn_index, question)
            row_count = len(data)
            return _build_sql_result_response(sql, data, session_id, turn_index, row_count, full_save)
        except Exception as e:
            logger.warning(f"[{session_id[:8]}] [QueryAgent] SQL执行失败，准备重试: {e}")
            try:
                sql_corrected = await generate_sql(question, vectordb, retry=True, previous_sql=previous_sql)
                data2, answer_text2, full_save2 = await _execute_and_save_sql(
                    db, sql_corrected, user_id, session_id, turn_index, question, is_retry=True)
                row_count2 = len(data2)
                return _build_sql_result_response(sql_corrected, data2, session_id, turn_index, row_count2, full_save2)
            except Exception as e2:
                logger.error(f"[{session_id[:8]}] [QueryAgent] SQL重试失败: 原始错误={e}, 修正错误={e2}")
                raise BusinessException(message=f"SQL执行失败: {str(e)}\n原始SQL: {sql}\n修正SQL: {sql_corrected}")

    # ---------- 数据分析分支 ----------
    elif intent == "analysis":
        logger.info(f"[{session_id[:8]}] [QueryAgent] 进入数据分析分支")
        answer, aggregate_sql_used, raw_answer = await process_analysis_branch(
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
        logger.info(f"[{session_id[:8]}] [QueryAgent] 进入闲聊分支")
        answer = await process_chat_branch(
            db, user_id, session_id, turn_index, question, include_history)
        return {
            "type": "answer",
            "session_id": session_id,
            "turn_index": turn_index,
            "answer": answer
        }


# ========== 流式输出支持 ==========



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
        logger.warning(f"[{session_id[:8]}] [QueryAgent] SQL执行失败，尝试重试: {e}")
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

    data_context, knowledge_context, aggregate_sql_used = await build_analysis_context(
        db, user_id, session_id, question, True, vectordb)

    question_safe = sanitize_prompt_input(question)
    data_context_safe = sanitize_prompt_input(data_context)
    knowledge_context_safe = sanitize_prompt_input(knowledge_context)

    analysis_prompt = _load_prompt("analysis_prompt").format(
        data_context=data_context_safe,
        knowledge_context=knowledge_context_safe,
        hist_text="",
        question=question_safe,
    )

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

    question_safe = sanitize_prompt_input(question)
    chat_history_safe = sanitize_prompt_input(chat_history_text)

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
        logger.info(f"[{session_id[:8]}] [QueryAgent] 流式处理 - 意图: {intent}")
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
        logger.error(f"[{session_id[:8]}] [QueryAgent] 流式处理异常: {e}")
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
        logger.error(f"[QueryAgent] LLM流式调用失败: {e}")
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
        logger.info(f"[{session_id[:8]}] [QueryAgent] 新会话")

    logger.info(f"[{session_id[:8]}] [QueryAgent] 流式请求: {question[:50]}...")

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
            logger.error(f"[QueryAgent] SSE生成器异常: {e}")
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
