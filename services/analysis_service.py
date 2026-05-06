"""数据分析逻辑"""
import json
from typing import Optional, List, Any

from services.llm_service import get_llm_client, get_llm_model, get_llm_temperature
from services.intent_classifier import sanitize_prompt_input
from services.sql_generator import (
    generate_aggregate_sql,
    execute_sql_to_dict,
    similarity_search_async,
)
from dao.conversation_dao import save_turn, get_recent_turns, get_latest_turn
from utils.json_encoder import safe_json_dumps
from utils.logger import get_logger
from prompts.loader import load_prompt

logger = get_logger("analysis_service")

ANALYSIS_REFINE_PROMPT = load_prompt("analysis_refine")
ANALYSIS_PROMPT = load_prompt("analysis_prompt")

# 常量（与 api/query_agent.py 的 QueryConstants 保持一致）
MAX_CONTEXT_CHARS = 5000
MAX_KNOWLEDGE_CHARS = 3000
MAX_SAMPLE_ROWS = 10


def summarize_result(
    data: List[dict],
    max_sample_rows: int = 3,
    full_save: bool = False,
) -> str:
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
        return safe_json_dumps(data, ensure_ascii=False)

    row_count = len(data)
    sample = data[:max_sample_rows]
    stats = {}
    for key in data[0].keys():
        if isinstance(data[0].get(key), (int, float)):
            values = [row.get(key) for row in data if row.get(key) is not None]
            if values:
                stats[key] = {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
    summary = {"row_count": row_count, "sample": sample, "statistics": stats}
    return safe_json_dumps(summary, ensure_ascii=False)


async def refine_analysis(raw_analysis: str) -> str:
    """对原始分析结果进行精简和规范化"""
    prompt = ANALYSIS_REFINE_PROMPT.format(raw_analysis=raw_analysis)
    client = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
        )
        refined = resp.choices[0].message.content.strip()
        return refined
    except Exception as e:
        logger.warning(f"精炼分析失败: {e}，返回原始结果")
        return raw_analysis


async def build_analysis_context(
    db,
    user_id: int,
    session_id: str,
    question: str,
    include_history: bool,
    vectordb,
    limit: int = 5,
) -> tuple[str, str, Optional[str]]:
    """
    构建数据分析所需的上下文信息

    返回: (data_context, knowledge_context, aggregate_sql_used)
    """
    data_context = ""
    knowledge_context = ""
    aggregate_sql_used = None

    latest_turn = get_latest_turn(db, user_id, session_id)
    if latest_turn and latest_turn.result_summary:
        try:
            if latest_turn.full_data_saved:
                full_data = json.loads(latest_turn.result_summary)
                data_context = (
                    f"上一轮查询得到的完整数据（共{len(full_data)}条）：\n"
                    f"{safe_json_dumps(full_data, indent=2)[:MAX_CONTEXT_CHARS]}\n"
                )
            else:
                original_desc = latest_turn.question
                aggregate_sql = await generate_aggregate_sql(question, original_desc, vectordb)
                if aggregate_sql:
                    agg_data = await execute_sql_to_dict(db, aggregate_sql)
                    agg_summary = summarize_result(agg_data, full_save=False)
                    data_context = f"根据您的分析需求，自动生成的聚合数据：\n{agg_summary}\n"
                    aggregate_sql_used = aggregate_sql
                else:
                    data_context = (
                        "上一轮查询数据量较大，无法直接分析，且自动生成聚合SQL失败。"
                        "请提出更具体的统计需求（例如：按分数段统计人数）。\n"
                    )
        except Exception as e:
            data_context = f"读取上一轮数据失败：{str(e)}\n"
    else:
        data_context = "未找到上一轮的数据。请先执行一次SQL查询，再进行分析。\n"

    if vectordb:
        docs = await similarity_search_async(vectordb, question, k=3)
        if docs:
            knowledge_context = "\n\n".join(
                [doc.page_content for doc in docs]
            )[:MAX_KNOWLEDGE_CHARS]

    return data_context, knowledge_context, aggregate_sql_used


async def process_analysis_branch(
    db,
    user_id: int,
    session_id: str,
    turn_index: int,
    question: str,
    include_history: bool,
    vectordb,
) -> tuple[str, Optional[str], str]:
    """
    处理数据分析意图

    返回: (answer, aggregate_sql_used, raw_answer)
    """
    analysis_history = (
        get_recent_turns(db, user_id, session_id, limit=5) if include_history else []
    )
    data_context, knowledge_context, aggregate_sql_used = await build_analysis_context(
        db, user_id, session_id, question, include_history, vectordb,
    )

    hist_text = "\n".join([
        f"用户: {turn.question}\n系统: {turn.answer_text[:200] if turn.answer_text else ''}"
        for turn in analysis_history
    ])

    question_safe = sanitize_prompt_input(question)
    data_context_safe = sanitize_prompt_input(data_context)
    knowledge_context_safe = sanitize_prompt_input(knowledge_context)
    hist_text_safe = sanitize_prompt_input(hist_text)

    analysis_prompt = ANALYSIS_PROMPT.format(
        data_context=data_context_safe,
        knowledge_context=knowledge_context_safe,
        hist_text=hist_text_safe,
        question=question_safe,
    )

    client = get_llm_client()
    try:
        resp_raw = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=get_llm_temperature(),
        )
        raw_answer = resp_raw.choices[0].message.content
        refined_answer = await refine_analysis(raw_answer)
        answer = refined_answer

        save_turn(db, user_id, session_id, turn_index, question,
                  answer_text=answer,
                  aggregate_sql=aggregate_sql_used,
                  full_data_saved=False)
        logger.info(f"[{session_id[:8]}] 数据分析完成")
        return answer, aggregate_sql_used, raw_answer
    except Exception as e:
        logger.error(f"[{session_id[:8]}] 分析失败: {e}")
        raise


async def process_chat_branch(
    db,
    user_id: int,
    session_id: str,
    turn_index: int,
    question: str,
    include_history: bool,
) -> str:
    """处理闲聊意图"""
    chat_history = (
        get_recent_turns(db, user_id, session_id, limit=5) if include_history else []
    )
    chat_history_text = "\n".join([
        f"用户: {turn.question}\n助手: {turn.answer_text}"
        for turn in chat_history
    ])

    question_safe = sanitize_prompt_input(question)
    chat_history_safe = sanitize_prompt_input(chat_history_text)

    if chat_history_safe:
        chat_prompt = (
            f"以下是用户与助手的对话历史。请根据历史回答用户的问题。"
            f"如果历史中有相关信息，请引用。\n\n"
            f"{chat_history_safe}\n\n用户最新问题：{question_safe}\n助手："
        )
    else:
        chat_prompt = f"用户：{question_safe}\n助手："

    client = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": chat_prompt}],
            temperature=get_llm_temperature(),
        )
        answer = resp.choices[0].message.content
        save_turn(db, user_id, session_id, turn_index, question, answer_text=answer)
        logger.info(f"[{session_id[:8]}] 闲聊回复完成")
        return answer
    except Exception as e:
        logger.error(f"[{session_id[:8]}] 闲聊失败: {e}")
        raise
