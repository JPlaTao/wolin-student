"""
对话式 BI — SSE 流式端点

POST /bi/stream  — LangGraph Agent SSE 流式问答
POST /bi/data-page — SQL 翻页（复用缓存 SQL 重执行，不走 Agent）
"""

import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from langchain_core.messages import HumanMessage, AIMessage

from core.database import get_db
from core.auth import get_current_user
from core.exceptions import NotFoundException
from model.user import User
from dao.conversation_dao import save_turn, get_recent_turns, get_turn_count
from services.bi_agent import build_bi_agent, get_cached_sql
from services.sql_generator import fix_table_names, validate_sql
from utils.logger import get_logger

logger = get_logger("bi_agent_api")

router = APIRouter(prefix="/bi", tags=["对话式BI"])


# ── 请求模型 ────────────────────────────────────────

class BIStreamRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class PageRequest(BaseModel):
    sql_hash: str
    page: int = 1
    page_size: int = 50


# ── SSE 格式化 ──────────────────────────────────────

def _sse(event_type: str, data) -> str:
    """格式化 SSE 事件"""
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"


# ── LangGraph 事件 → SSE 事件映射 ────────────────────

def _convert_langgraph_event(event: dict) -> Optional[str]:
    """
    将 LangGraph astream_events 输出转换为 SSE 事件字符串。
    返回 None 表示该事件无需推送给前端。
    """
    kind = event["event"]
    name = event.get("name", "")

    if kind == "on_chat_model_stream":
        chunk = event["data"].get("chunk")
        if chunk and hasattr(chunk, "content") and chunk.content:
            content = chunk.content
            if isinstance(content, list):
                # 部分模型返回 [{"text": "...", "type": "text"}]
                text = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            else:
                text = str(content)
            if text:
                return _sse("chunk", text)
        return None

    if kind == "on_tool_start":
        tool_name = name
        tool_input = event["data"].get("input", {})
        events = []
        hint_map = {
            "generate_sql": "正在生成 SQL 查询...",
            "execute_sql": "正在执行查询...",
            "analyze_data": "正在分析数据...",
        }
        hint = hint_map.get(tool_name, f"正在执行: {tool_name}")
        events.append(_sse("thinking", hint))
        # 只对非数据密集型工具推送完整参数
        if tool_name != "analyze_data":
            events.append(_sse("tool_call", {"tool": tool_name, "args": tool_input}))
        else:
            events.append(_sse("tool_call", {"tool": tool_name, "args": {"question": tool_input.get("question", "")}}))
        return "".join(events)

    if kind == "on_tool_end":
        tool_name = name
        output = event["data"].get("output")
        if hasattr(output, "content"):
            content = output.content
        elif isinstance(output, str):
            content = output
        else:
            content = str(output)

        if tool_name == "generate_sql":
            # content 是 SQL 字符串
            import hashlib
            sql_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            return _sse("sql", {"sql": content, "sql_hash": sql_hash})

        if tool_name == "execute_sql":
            # content 是 JSON 字符串，解析后推送
            try:
                data = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                data = {"raw": str(content)[:500]}
            return _sse("data", data)

        if tool_name == "analyze_data":
            try:
                data = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                data = {"raw": str(content)[:500]}
            return _sse("analysis", data)

        return None

    # 过滤不应暴露的内部事件
    return None


# ── SSE 流式端点 ────────────────────────────────────

@router.post("/stream")
async def bi_stream(req: BIStreamRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """
    对话式 BI 流式接口

    使用 LangGraph Agent 自动编排 SQL 生成 → 执行 → 分析 → 回复。
    SSE 事件类型: thinking, tool_call, sql, data, analysis, chunk, done, error
    """
    question = req.question.strip()
    user_id = current_user.id
    session_id = req.session_id or f"bi_{uuid.uuid4().hex[:12]}"

    logger.info(f"[{session_id[:16]}] [BI-Agent] 流式请求: {question[:60]}...")

    # 加载历史（最近 5 轮）
    history_turns = get_recent_turns(db, user_id, session_id, limit=5)
    turn_index = get_turn_count(db, user_id, session_id) + 1

    # 构建初始消息列表
    initial_messages = []
    for turn in history_turns:
        initial_messages.append(HumanMessage(content=turn.question))
        if turn.answer_text:
            initial_messages.append(AIMessage(content=turn.answer_text))

    # 如果当前问题已在历史中（重试场景），不重复添加
    if not initial_messages or initial_messages[-1].content != question:
        initial_messages.append(HumanMessage(content=question))

    agent, result_store = build_bi_agent(db, user_id, session_id)

    async def event_generator():
        full_answer = ""
        try:
            async for event in agent.astream_events(
                {"messages": initial_messages},
                version="v2",
            ):
                sse_str = _convert_langgraph_event(event)
                if sse_str:
                    # 收集 AI 文本回复用于保存
                    if event["event"] == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                            if isinstance(content, str):
                                full_answer += content
                            elif isinstance(content, list):
                                full_answer += "".join(
                                    c.get("text", "") for c in content if isinstance(c, dict))

                    await asyncio.sleep(0.01)
                    yield sse_str

            yield _sse("done", "")

        except Exception as e:
            logger.error(f"[{session_id[:16]}] Agent 执行失败: {e}")
            yield _sse("error", str(e))
            return

        # 保存本轮对话
        try:
            sql = result_store.get("sql", "")
            query_result = result_store.get("query_result")
            analysis_result = result_store.get("analysis_result")

            result_summary = None
            if query_result and query_result.get("success"):
                summary = {
                    "row_count": query_result.get("row_count"),
                    "statistics": query_result.get("statistics"),
                    "sql_hash": query_result.get("sql_hash"),
                    "columns": query_result.get("columns", []),
                }
                # 保存第一页数据，用于刷新后恢复表格和图表
                row_count = query_result.get("row_count", 0)
                if row_count <= 100:
                    summary["rows"] = query_result.get("rows", [])
                if analysis_result:
                    analysis = analysis_result if isinstance(analysis_result, dict) else None
                    if analysis:
                        chart = analysis.get("chart_suggestion")
                        summary["analysis"] = {
                            "key_findings": analysis.get("key_findings", []),
                            "chart_suggestion": chart,
                        }
                result_summary = json.dumps(summary, ensure_ascii=False)

            answer_text = full_answer.strip()
            if not answer_text:
                answer_text = None

            save_turn(
                db=db,
                user_id=user_id,
                session_id=session_id,
                turn_index=turn_index,
                question=question,
                sql_query=sql or None,
                result_summary=result_summary,
                answer_text=answer_text,
                full_data_saved=bool(query_result and query_result.get("row_count", 0) <= 100),
            )
            logger.info(f"[{session_id[:16]}] 对话已保存: turn={turn_index}")
        except Exception as e:
            logger.error(f"[{session_id[:16]}] 保存对话失败: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ── 分页翻页端点 ────────────────────────────────────

@router.post("/data-page")
async def bi_data_page(req: PageRequest, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """
    根据 sql_hash 获取指定页数据。
    不经过 Agent，直接执行缓存的 SQL + LIMIT/OFFSET。
    """
    sql = get_cached_sql(req.sql_hash)
    if not sql:
        raise NotFoundException("SQL 已过期，请重新查询")

    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise NotFoundException(f"缓存的 SQL 无效: {error_msg}")

    offset = (req.page - 1) * req.page_size
    paginated_sql = f"{sql.rstrip(';')} LIMIT {req.page_size} OFFSET {offset}"

    import asyncio as _asyncio
    def _sync():
        r = db.execute(text(paginated_sql))
        rows = r.fetchall()
        return [dict(zip(r.keys(), row)) for row in rows] if rows else []

    rows = await _asyncio.to_thread(_sync)

    return {
        "code": 200,
        "data": {
            "sql_hash": req.sql_hash,
            "page": req.page,
            "page_size": req.page_size,
            "rows": rows,
        }
    }


# ── 会话管理端点 ────────────────────────────────────

@router.get("/sessions")
async def bi_list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有会话列表（含摘要）"""
    from dao.conversation_dao import list_sessions as _list_sessions
    sessions = _list_sessions(db, current_user.id)
    return {"code": 200, "data": sessions}


@router.get("/sessions/{session_id}")
async def bi_get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定会话的全部消息"""
    from dao.conversation_dao import get_all_turns
    turns = get_all_turns(db, current_user.id, session_id)

    messages = []
    for turn in turns:
        result_summary = None
        if turn.result_summary:
            try:
                result_summary = json.loads(turn.result_summary)
            except (json.JSONDecodeError, TypeError):
                result_summary = turn.result_summary

        messages.append({
            "turn_index": turn.turn_index,
            "question": turn.question,
            "answer_text": turn.answer_text,
            "sql_query": turn.sql_query,
            "result_summary": result_summary,
            "created_at": turn.created_at.isoformat() if turn.created_at else None,
        })

    return {"code": 200, "data": messages}
