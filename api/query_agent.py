import os
import re
import asyncio
import uuid
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import AsyncOpenAI
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from database import get_db
from dao.conversation_dao import save_turn, get_recent_turns, get_turn_count, get_latest_turn, get_previous_sql_turn

load_dotenv()

router = APIRouter(prefix="/query", tags=["自然语言查询"])

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ---------- 向量知识库 ----------
vectordb = None
try:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("警告: 未设置 DASHSCOPE_API_KEY，知识库功能不可用")
    else:
        embeddings = DashScopeEmbeddings(model="text-embedding-v3", dashscope_api_key=api_key)
        if os.path.exists("./chroma_db") and os.path.isdir("./chroma_db"):
            vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            print("向量知识库加载成功")
        else:
            print("知识库目录不存在，请先运行 build_knowledge_base() 构建")
except Exception as e:
    print(f"向量知识库加载失败: {e}")

# ---------- 请求模型 ----------
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    include_history: bool = True

# ---------- 备用表结构 ----------
FALLBACK_SCHEMA = """
数据库表结构（简化版）：
- teacher: teacher_id, teacher_name, gender, phone, role, is_deleted (BOOLEAN)
- class: class_id, class_name, start_time, head_teacher_id, is_deleted (BOOLEAN)
- stu_basic_info: stu_id, stu_name, native_place, graduated_school, major, admission_date, graduation_date, education, age, gender, advisor_id, class_id, is_deleted (BOOLEAN)
- stu_exam_record: stu_id, seq_no, grade, exam_date, is_deleted (INT, 0=未删除)
- employment: emp_id, stu_id, stu_name, class_id, open_time, offer_time, company, salary, is_deleted (BOOLEAN)

重要规则：
- 所有查询必须过滤 is_deleted = 0 或 False（成绩表用 is_deleted = 0）
- 表名均为单数形式，不要使用复数
- 只生成 SELECT 语句
"""

# ---------- 辅助函数 ----------
def fix_table_names(sql: str) -> str:
    sql = re.sub(r'\bteachers\b', 'teacher', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bstudents\b', 'stu_basic_info', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bcourses\b', 'class', sql, flags=re.IGNORECASE)
    return sql

async def similarity_search_async(vectordb, query: str, k: int = 3):
    def _sync():
        return vectordb.similarity_search(query, k=k)
    return await asyncio.to_thread(_sync)

async def retrieve_schema_context(vectordb) -> str:
    if vectordb is None:
        return FALLBACK_SCHEMA
    try:
        docs = await similarity_search_async(vectordb, "数据库表结构 字段定义 表名", k=2)
        if docs:
            context = "\n\n".join([doc.page_content for doc in docs])
            return context[:4000]
    except Exception as e:
        print(f"检索表结构失败: {e}")
    return FALLBACK_SCHEMA

def summarize_result(data: List[dict], max_sample_rows: int = 3, full_save: bool = False) -> str:
    """
    生成结果摘要或完整数据JSON。
    如果 full_save=True，则返回完整JSON（注意可能很大）。
    否则返回摘要（包含 row_count, sample, statistics）。
    """
    if not data:
        return json.dumps({"row_count": 0, "sample": []})
    if full_save:
        # 完整保存，直接序列化全部数据（可能很大，但用户要求）
        return json.dumps(data, ensure_ascii=False, default=str)
    else:
        row_count = len(data)
        sample = data[:max_sample_rows]
        stats = {}
        for key in data[0].keys():
            if isinstance(data[0].get(key), (int, float)):
                values = [row.get(key) for row in data if row.get(key) is not None]
                if values:
                    stats[key] = {"avg": sum(values)/len(values), "min": min(values), "max": max(values)}
        summary = {"row_count": row_count, "sample": sample, "statistics": stats}
        return json.dumps(summary, ensure_ascii=False, default=str)

# ---------- 意图分类 ----------
INTENT_CLASSIFICATION_PROMPT = """
你是一个意图分类助手。根据对话历史和当前用户问题，判断用户意图。

历史对话（最近5轮）：
{history}

当前问题：{question}

意图选项（只输出一个单词）：
- sql: 用户需要从数据库查询具体数据（如“查询成绩”、“统计人数”、“列出学生”）
- analysis: 用户希望进行数据分析、解释原因、对比趋势（如“为什么成绩低”、“分析就业率变化”）
- chat: 其他日常闲聊、问候、无关问题

意图：
"""

async def classify_intent_llm(question: str, history_text: str = "") -> str:
    if history_text:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(history=history_text, question=question)
    else:
        prompt = f"意图选项：sql / analysis / chat\n用户问题：{question}\n意图："
    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10
        )
        intent = resp.choices[0].message.content.strip().lower()
        if intent in ["sql", "analysis", "chat"]:
            return intent
    except Exception as e:
        print(f"LLM意图分类失败: {e}，降级到关键词匹配")
    # 降级关键词
    knowledge_keywords = ["为什么", "什么原因", "解释", "说明", "含义", "规则", "定义", "分析", "分布", "趋势", "对比"]
    if any(kw in question for kw in knowledge_keywords):
        return "analysis"
    sql_keywords = ["查询", "多少", "几个", "平均", "最高", "最低", "排名", "列表", "统计", "每个", "各个", "薪资", "年龄", "成绩", "学生", "班级", "老师", "就业", "考试"]
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
- 如果用户明确提到“刚才”、“上一轮”、“再查一下”、“同样的”、“也”、“那个”、“再次”、“同样”等词，或者明显引用上一轮的结果（如“那个班的就业率”），返回 "YES"。
- 否则返回 "NO"。

只输出 YES 或 NO。
"""

async def check_sql_reference(question: str, history_text: str) -> str:
    prompt = SQL_REFERENCE_CHECK_PROMPT.format(history=history_text, question=question)
    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10
        )
        result = resp.choices[0].message.content.strip().upper()
        if result in ["YES", "NO"]:
            return result
    except Exception as e:
        print(f"SQL引用检测失败: {e}")
    # 降级关键词
    reference_keywords = ["刚才", "上一轮", "再查", "同样的", "也", "那个", "再次", "同样", "这个班", "那个班"]
    if any(kw in question for kw in reference_keywords):
        return "YES"
    return "NO"

# ---------- SQL 生成 ----------
async def generate_sql(question: str, vectordb, retry: bool = False, previous_sql: Optional[str] = None) -> str:
    system = "你是一个MySQL专家，只输出SQL语句，不要有任何额外解释。以分号结尾。表名都是单数。"
    if retry:
        system += " 上一次生成的SQL执行失败，请修正。只输出修正后的SQL语句。"
    schema = await retrieve_schema_context(vectordb)
    user = f"数据库结构：\n{schema}\n\n用户问题：{question}\n输出SQL："
    if previous_sql:
        user = f"上一轮用户执行的SQL是：\n{previous_sql}\n\n用户现在的问题可能希望复用其中的过滤条件。\n\n数据库结构：\n{schema}\n\n用户问题：{question}\n输出SQL："
    resp = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.1,
    )
    sql = resp.choices[0].message.content.strip()
    sql = re.sub(r'^```sql\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)
    return fix_table_names(sql)

async def execute_sql_to_dict(db: Session, sql: str):
    def _sync():
        result = db.execute(text(sql))
        rows = result.fetchall()
        if not rows:
            return []
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

async def generate_aggregate_sql(question: str, original_desc: str, vectordb) -> Optional[str]:
    schema = await retrieve_schema_context(vectordb)
    prompt = AGGREGATE_SQL_PROMPT.format(schema=schema, question=question, original_desc=original_desc)
    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        sql = resp.choices[0].message.content.strip()
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        if sql.lower().startswith("select"):
            return fix_table_names(sql)
    except Exception as e:
        print(f"生成聚合SQL失败: {e}")
    return None

# ---------- 数据分析精炼 ----------
ANALYSIS_REFINE_PROMPT = """
你是一个数据分析专家，请对以下初步分析结果进行精简和规范化。

要求：
- 删除重复的句子或观点
- 合并相似结论
- 去掉无意义的填充词（如“总的来说”、“首先呢”、“那么”等）
- 保留关键数据、原因、建议
- 输出结构：结论 → 数据支撑 → 可能原因 → 建议

原始分析结果：
{raw_analysis}

请输出精炼后的最终回答：
"""

async def refine_analysis(raw_analysis: str) -> str:
    prompt = ANALYSIS_REFINE_PROMPT.format(raw_analysis=raw_analysis)
    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        refined = resp.choices[0].message.content.strip()
        return refined
    except Exception as e:
        print(f"精炼分析失败: {e}，返回原始结果")
        return raw_analysis

# ---------- 主接口 ----------
@router.post("/natural")
async def natural_query(req: QueryRequest, db: Session = Depends(get_db)):
    question = req.question
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        print(f"警告: 未提供 session_id，已生成新会话: {session_id}。后续请求请携带此ID以维持多轮记忆。")
    include_history = req.include_history

    # 获取历史记忆（用于意图分类和闲聊/分析）
    history_turns = get_recent_turns(db, session_id, limit=5) if include_history else []
    print(f"会话 {session_id} 历史记录数: {len(history_turns)}")
    history_text = ""
    for turn in history_turns:
        if turn.result_summary:
            summary_preview = turn.result_summary[:200]
        else:
            summary_preview = turn.answer_text[:200] if turn.answer_text else ""
        history_text += f"用户: {turn.question}\n系统: {summary_preview}\n"

    # 意图分类
    intent = await classify_intent_llm(question, history_text)
    print(f"意图分类结果: {intent}")

    turn_index = get_turn_count(db, session_id) + 1

    # ---------- SQL 分支 ----------
    if intent == "sql":
        # 检查是否需要引用上一轮SQL
        need_reference = False
        previous_sql_turn = None
        if history_turns:
            # 获取上一轮有SQL的记录（可能不是最新一轮，但通常是）
            previous_sql_turn = get_previous_sql_turn(db, session_id)
            if previous_sql_turn and previous_sql_turn.sql_query:
                # 只取最近2轮历史用于判断
                recent_2 = history_turns[-2:] if len(history_turns) >= 2 else history_turns
                ref_history = "\n".join([f"用户: {t.question}\n系统: {t.answer_text[:100] if t.answer_text else ''}" for t in recent_2])
                reference_check = await check_sql_reference(question, ref_history)
                need_reference = (reference_check == "YES")
                print(f"SQL引用检测结果: {reference_check}")

        try:
            if need_reference and previous_sql_turn and previous_sql_turn.sql_query:
                sql = await generate_sql(question, vectordb, retry=False, previous_sql=previous_sql_turn.sql_query)
            else:
                sql = await generate_sql(question, vectordb, retry=False)
        except Exception as e:
            raise HTTPException(500, f"生成SQL失败: {e}")

        if not sql.strip().lower().startswith("select"):
            raise HTTPException(400, "只能生成SELECT语句")

        try:
            data = await execute_sql_to_dict(db, sql)
            row_count = len(data)
            # 判断是否全量保存：行数<=100 且 JSON序列化后长度<=2000
            full_save = (row_count <= 100) and (len(json.dumps(data, default=str)) <= 2000)
            if full_save:
                result_summary = summarize_result(data, full_save=True)
                answer_text = f"查询成功，共{row_count}条记录。"
            else:
                result_summary = summarize_result(data, full_save=False)  # 摘要
                answer_text = f"数据量较大（共{row_count}行），已为您存储分析标记。您可以继续提问“分析这些数据”。"
            save_turn(db, session_id, turn_index, question, sql_query=sql, result_summary=result_summary, answer_text=answer_text, full_data_saved=full_save)
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
                # 返回前10行样本
                sample_data = data[:10]
                return {
                    "type": "sql",
                    "session_id": session_id,
                    "turn_index": turn_index,
                    "sql": sql,
                    "data_truncated": True,
                    "sample_data": sample_data,
                    "message": answer_text,
                    "full_data_saved": False
                }
        except Exception as e:
            # 重试一次
            try:
                sql_corrected = await generate_sql(question, vectordb, retry=True)
                data2 = await execute_sql_to_dict(db, sql_corrected)
                row_count2 = len(data2)
                full_save2 = (row_count2 <= 100) and (len(json.dumps(data2, default=str)) <= 2000)
                if full_save2:
                    result_summary2 = summarize_result(data2, full_save=True)
                    answer_text2 = f"查询成功，共{row_count2}条记录。"
                else:
                    result_summary2 = summarize_result(data2, full_save=False)
                    answer_text2 = f"数据量较大（共{row_count2}行），已为您存储分析标记。"
                save_turn(db, session_id, turn_index, question, sql_query=sql_corrected, result_summary=result_summary2, answer_text=answer_text2, full_data_saved=full_save2)
                if full_save2:
                    return {
                        "type": "sql",
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "sql": sql_corrected,
                        "data": data2,
                        "count": row_count2,
                        "full_data_saved": True
                    }
                else:
                    return {
                        "type": "sql",
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "sql": sql_corrected,
                        "data_truncated": True,
                        "sample_data": data2[:10],
                        "message": answer_text2,
                        "full_data_saved": False
                    }
            except Exception as e2:
                raise HTTPException(500, f"SQL执行失败: {str(e)}\n原始SQL: {sql}\n修正SQL: {sql_corrected}")

    # ---------- 数据分析分支 ----------
    elif intent == "analysis":
        # 读取最近5轮历史（用于上下文）
        analysis_history = get_recent_turns(db, session_id, limit=5) if include_history else []
        # 获取上一轮（最新一轮）数据
        latest_turn = get_latest_turn(db, session_id)
        data_context = ""
        aggregate_sql_used = None
        need_aggregate = False

        # 判断是否需要上一轮数据：如果用户问题包含“这些数据”、“刚才的结果”等，则默认需要；否则也可以不需要
        # 简化：如果上一轮存在且有 result_summary，则尝试使用
        if latest_turn and latest_turn.result_summary:
            try:
                if latest_turn.full_data_saved:
                    # 全量保存，直接读取完整数据
                    full_data = json.loads(latest_turn.result_summary)
                    data_context = f"上一轮查询得到的完整数据（共{len(full_data)}条）：\n{json.dumps(full_data, ensure_ascii=False, indent=2)[:5000]}\n"
                else:
                    # 非全量，尝试生成聚合SQL
                    need_aggregate = True
                    # 从摘要中获取原始问题描述
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

        # 知识库检索
        knowledge_context = ""
        if vectordb:
            docs = await similarity_search_async(vectordb, question, k=3)
            if docs:
                knowledge_context = "\n\n".join([doc.page_content for doc in docs])[:3000]

        # 构建历史文本（最近5轮）
        hist_text = ""
        for turn in analysis_history:
            hist_text += f"用户: {turn.question}\n系统: {turn.answer_text[:200] if turn.answer_text else ''}\n"

        # 第一轮：粗分析
        analysis_prompt = f"""
你是一个数据分析专家。请**严格基于以下提供的数据**回答用户的分析问题。不要编造数据。

【提供的数据】
{data_context}

【参考分析指南】
{knowledge_context}

【历史对话记录（仅供参考）】
{hist_text}

【用户问题】
{question}

请给出清晰的分析结论、可能的原因和建议。如果数据不足，请明确指出缺少哪些数据，而不是给出通用回答。
"""
        try:
            resp_raw = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.5,
            )
            raw_answer = resp_raw.choices[0].message.content
            # 第二轮：精炼
            refined_answer = await refine_analysis(raw_answer)
            answer = refined_answer
            # 保存记录（注意：result_summary 这里存储的是数据上下文摘要，但为了节省空间，可以只存聚合SQL或标记）
            save_turn(db, session_id, turn_index, question, answer_text=answer, aggregate_sql=aggregate_sql_used, full_data_saved=False)
            return {
                "type": "answer",
                "session_id": session_id,
                "turn_index": turn_index,
                "answer": answer,
                "raw_analysis": raw_answer  # 可选，调试用
            }
        except Exception as e:
            raise HTTPException(500, f"分析失败: {str(e)}")

    # ---------- 闲聊分支 ----------
    else:
        # 读取最近5轮历史
        chat_history = get_recent_turns(db, session_id, limit=5) if include_history else []
        chat_history_text = ""
        for turn in chat_history:
            chat_history_text += f"用户: {turn.question}\n助手: {turn.answer_text}\n"
        if chat_history_text:
            chat_prompt = f"以下是用户与助手的对话历史。请根据历史回答用户的问题。如果历史中有相关信息，请引用。\n\n{chat_history_text}\n\n用户最新问题：{question}\n助手："
        else:
            chat_prompt = f"用户：{question}\n助手："
        try:
            resp = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": chat_prompt}],
                temperature=0.7,
            )
            answer = resp.choices[0].message.content
            save_turn(db, session_id, turn_index, question, answer_text=answer)
            return {
                "type": "answer",
                "session_id": session_id,
                "turn_index": turn_index,
                "answer": answer
            }
        except Exception as e:
            raise HTTPException(500, f"闲聊失败: {str(e)}")