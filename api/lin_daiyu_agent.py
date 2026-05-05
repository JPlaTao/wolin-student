"""林黛玉 Agent — FastAPI 路由与端点"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from model.user import User
from dao.conversation_dao import save_turn, get_recent_turns, get_turn_count
from services.lin_daiyu_service import (
    generate_response,
    build_conversation_messages,
    DAIYU_GREETING,
)
from utils.logger import get_logger

logger = get_logger("lin_daiyu_api")

router = APIRouter(prefix="/api/daiyu", tags=["林黛玉智能助手"])


# ---------- 请求/响应模型 ----------
class DaiyuChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class DaiyuChatResponse(BaseModel):
    session_id: str
    turn_index: int
    answer: str


# ---------- 非流式对话 ----------
@router.post("/chat", response_model=DaiyuChatResponse)
async def daiyu_chat(
    req: DaiyuChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """林黛玉智能助手 — 非流式对话"""
    user_id = current_user.id
    session_id = req.session_id or f"ldy_{user_id}_{uuid.uuid4().hex[:12]}"

    history = get_recent_turns(db, user_id, session_id, limit=10)
    turn_index = get_turn_count(db, user_id, session_id) + 1

    answer = await generate_response(
        question=req.question,
        history_turns=history,
    )

    save_turn(db, user_id, session_id, turn_index, req.question, answer_text=answer)

    logger.info(f"[{session_id[:8]}] [DaiyuAPI] 非流式对话完成 (turn={turn_index})")

    return DaiyuChatResponse(
        session_id=session_id,
        turn_index=turn_index,
        answer=answer,
    )


# ---------- 流式对话 (SSE) ----------
@router.post("/stream")
async def daiyu_stream(
    req: DaiyuChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """林黛玉智能助手 — SSE 流式对话"""
    user_id = current_user.id
    session_id = req.session_id or f"ldy_{user_id}_{uuid.uuid4().hex[:12]}"

    history = get_recent_turns(db, user_id, session_id, limit=10)
    turn_index = get_turn_count(db, user_id, session_id) + 1

    messages = build_conversation_messages(
        question=req.question,
        history_turns=history,
    )

    async def event_generator():
        full_response = ""
        try:
            from services.lin_daiyu_service import llm_config
            from services.lin_daiyu_service import client

            stream = await client.chat.completions.create(
                model=llm_config.model,
                messages=messages,
                temperature=0.85,
                stream=True,
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield f"event: chunk\ndata: {content}\n\n"

            yield "event: done\ndata: \n\n"

        except Exception as e:
            logger.error(f"[DaiyuAPI] 流式处理异常: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
            yield "event: done\ndata: \n\n"

        # 流结束后保存对话记录
        if full_response:
            save_turn(
                db, user_id, session_id, turn_index,
                req.question, answer_text=full_response,
            )
            logger.info(f"[{session_id[:8]}] [DaiyuAPI] 流式对话完成 (turn={turn_index})")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
