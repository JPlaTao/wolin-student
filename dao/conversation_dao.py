from sqlalchemy.orm import Session
from model.conversation import ConversationMemory
from typing import List, Optional, Dict, Any

def save_turn(
    db: Session,
    user_id: int,
    session_id: str,
    turn_index: int,
    question: str,
    sql_query: Optional[str] = None,
    result_summary: Optional[str] = None,
    answer_text: Optional[str] = None,
    full_data_saved: bool = False,
    aggregate_sql: Optional[str] = None,
    embedding_vector: Optional[Dict[str, Any]] = None
) -> ConversationMemory:
    """保存一轮对话记录"""
    record = ConversationMemory(
        user_id=user_id,
        session_id=session_id,
        turn_index=turn_index,
        question=question,
        sql_query=sql_query,
        result_summary=result_summary,
        answer_text=answer_text,
        full_data_saved=full_data_saved,
        aggregate_sql=aggregate_sql,
        embedding_vector=embedding_vector
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def get_recent_turns(db: Session, user_id: int, session_id: str, limit: int = 5) -> List[ConversationMemory]:
    """获取会话最近N轮对话（按轮次升序，即最早的在前面）"""
    records = db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id
    ).order_by(ConversationMemory.turn_index.desc()).limit(limit).all()
    return list(reversed(records))

def get_latest_turn(db: Session, user_id: int, session_id: str) -> Optional[ConversationMemory]:
    """获取会话最新一轮对话"""
    return db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id
    ).order_by(ConversationMemory.turn_index.desc()).first()

def get_turn_count(db: Session, user_id: int, session_id: str) -> int:
    """获取会话总轮次"""
    return db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id
    ).count()

def get_previous_sql_turn(db: Session, user_id: int, session_id: str) -> Optional[ConversationMemory]:
    """获取上一轮有 SQL 查询的记录（用于引用历史）"""
    return db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id,
        ConversationMemory.sql_query.isnot(None)
    ).order_by(ConversationMemory.turn_index.desc()).first()


def get_all_turns(db: Session, user_id: int, session_id: str) -> List[ConversationMemory]:
    """获取指定会话的全部轮次（按 turn_index 升序）"""
    return db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id
    ).order_by(ConversationMemory.turn_index.asc()).all()


def list_sessions(db: Session, user_id: int) -> list[dict]:
    """获取用户的所有会话摘要（含最后提问和轮次数量）"""
    from sqlalchemy import text as sql_text
    rows = db.execute(sql_text("""
        SELECT t.session_id, t.turn_count, t.last_time,
               (SELECT cm2.question FROM conversation_memory cm2
                WHERE cm2.user_id = :uid2 AND cm2.session_id = t.session_id
                ORDER BY cm2.turn_index DESC LIMIT 1) AS last_question
        FROM (
            SELECT session_id, COUNT(*) AS turn_count, MAX(created_at) AS last_time
            FROM conversation_memory
            WHERE user_id = :uid
            GROUP BY session_id
        ) t
        ORDER BY t.last_time DESC
    """), {"uid": user_id, "uid2": user_id}).fetchall()
    return [
        {
            "session_id": r[0],
            "turn_count": r[1],
            "last_time": r[2].isoformat() if r[2] else None,
            "last_question": r[3],
        }
        for r in rows
    ]