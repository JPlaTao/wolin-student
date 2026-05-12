"""
LangGraph Agent — 对话式 BI 核心

使用 LangGraph create_agent + 3 个 Tool 实现：
  1. generate_sql  — 自然语言 → SQL
  2. execute_sql  — 执行 SQL，返回分页数据 + 统计
  3. analyze_data — 结构化数据分析（AnalysisOutput）

架构：Agent 自行编排 Tool 调用顺序，一次对话可串联"生成→执行→分析"
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.orm import Session

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from core.settings import get_settings
from schemas.bi_analysis import AnalysisOutput
from utils.logger import get_logger

logger = get_logger("bi_agent")

# ── SQL 缓存（MD5 → SQL，30 分钟 TTL）────────────────
_sql_cache: Dict[str, tuple[str, float]] = {}  # {hash: (sql, expiry_time)}

_CACHE_TTL = 1800  # 30 分钟


def _cache_sql(sql: str) -> str:
    """缓存 SQL 并返回 hash"""
    h = hashlib.md5(sql.encode()).hexdigest()[:12]
    _sql_cache[h] = (sql, time.time() + _CACHE_TTL)
    return h


def get_cached_sql(sql_hash: str) -> str | None:
    """获取缓存的 SQL，过期返回 None"""
    entry = _sql_cache.get(sql_hash)
    if not entry:
        return None
    sql, expiry = entry
    if time.time() > expiry:
        del _sql_cache[sql_hash]
        return None
    return sql


# ── System Prompt ────────────────────────────────────

SYSTEM_PROMPT = """你是「沃林学生管理系统」的 AI 数据分析助手。

## 核心能力
你通过以下工具帮助用户：
1. **generate_sql** — 把自然语言问题转为 SQL 查询。可传入先前 SQL 作为 context 以复用过滤条件。
2. **execute_sql** — 执行 SQL 并获取结构化结果（含分页数据 + 列统计）。
3. **analyze_data** — 对查询结果进行数据分析，输出结构化分析（含图表建议）。

## 工作流程
- 用户提出数据问题 → 先生成 SQL → 执行查询 → 分析结果
- 用户要求分析但未指定数据 → 先查数据再分析
- 用户直接闲聊 → 不调工具，直接回复
- 如果执行 SQL 出错，检查错误信息并修正 SQL 后重试

## 重要规则
- 所有表名均为单数（teacher 不是 teachers，stu_basic_info 不是 students）
- 所有查询必须过滤 is_deleted = 0 或 is_deleted = FALSE
- 只生成 SELECT 语句
- 生成 SQL 时可以通过 context 参数引用之前的查询条件

## 数据字典
- teacher: teacher_id, teacher_name, gender, phone, role, is_deleted
- class: class_id, class_name, start_time, head_teacher_id, is_deleted
- class_teacher: class_id, teacher_id (多对多关联)
- stu_basic_info: stu_id, stu_name, native_place, graduated_school, major, admission_date, graduation_date, education, age, gender, advisor_id, class_id, is_deleted
- stu_exam_record: stu_id, seq_no, grade, exam_date, is_deleted (INT, 0=未删除)
- employment: emp_id, stu_id, stu_name, class_id, open_time, offer_time, company, salary, is_deleted

## 回答风格
- 先给出结论，再展示数据细节
- 如果数据适合图表展示，调用 analyze_data 获取图表建议
- 使用中文，简洁清晰
"""


# ── 入口函数 ────────────────────────────────────────

def build_bi_agent(db: Session, user_id: int, session_id: str) -> tuple:
    """
    构建 LangGraph BI Agent。

    Returns:
        (agent, result_store):
        - agent: 编译后的 LangGraph Agent（支持 ainvoke / astream_events）
        - result_store: 工具闭包写入的共享字典，API 层读取提取 SQL/data/analysis
    """
    result_store: Dict[str, Any] = {}

    llm = _create_llm()
    tools = _create_tools(db, result_store)

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        name="bi_agent",
    )

    logger.info(f"BI Agent 构建完成: user_id={user_id}, session_id={session_id}")
    return agent, result_store


# ── LLM 工厂 ────────────────────────────────────────

def _create_llm(temperature: float | None = None) -> ChatOpenAI:
    """根据 config.json 创建 LangChain ChatOpenAI 实例"""
    settings = get_settings()
    provider = settings.llm.provider.lower()

    api_key_map = {
        "kimi": settings.api_keys.kimi,
        "deepseek": settings.api_keys.deepseek,
        "openai": settings.api_keys.openai,
    }
    api_key = api_key_map.get(provider, settings.api_keys.kimi)

    temp = temperature if temperature is not None else settings.llm.effective_temperature

    return ChatOpenAI(
        model=settings.llm.model,
        api_key=api_key,
        base_url=settings.llm.base_url,
        temperature=temp,
    )


# ── 统计计算 ────────────────────────────────────────

def _compute_statistics(rows: list[dict]) -> dict:
    """对查询结果每列计算基本统计"""
    if not rows:
        return {}
    stats = {}
    for col in rows[0].keys():
        values = [row[col] for row in rows if row[col] is not None]
        if not values:
            continue
        if all(isinstance(v, (int, float)) for v in values):
            stats[col] = {
                "min": round(min(values), 2) if isinstance(min(values), float) else min(values),
                "max": round(max(values), 2) if isinstance(max(values), float) else max(values),
                "avg": round(sum(values) / len(values), 2),
            }
        elif all(isinstance(v, str) for v in values):
            stats[col] = {"distinct": len(set(values))}
    return stats


# ── 工具工厂 ────────────────────────────────────────

def _create_tools(db: Session, result_store: Dict[str, Any]) -> list:
    """
    创建 3 个 Agent Tool。
    通过闭包注入 db / result_store，避免暴露基础设施参数给 LLM。
    """
    async def generate_sql(question: str, context: str = "") -> str:
        """
        根据自然语言问题生成 SQL 查询语句。
        context 参数可选，传入之前的 SQL 或过滤条件以保持上下文连续性。
        返回: 纯 SQL 字符串（以分号结尾的 SELECT 语句）
        """
        from services.sql_generator import generate_sql as _gen_sql
        from services.vectordb import vectordb

        sql = await _gen_sql(
            question=question,
            vectordb=vectordb,
            retry=False,
            previous_sql=context if context else None,
        )

        result_store["sql"] = sql
        result_store["sql_hash"] = hashlib.md5(sql.encode()).hexdigest()[:12]

        logger.info(f"generate_sql 生成: {sql[:120]}...")
        return sql

    @tool
    async def execute_sql(sql: str, page: int = 1, page_size: int = 50) -> str:
        """
        执行只读 SQL 查询并返回分页结果 + 列统计。
        输入必须是完整的 SELECT 语句。
        返回 JSON 字符串，包含: success, columns, rows, row_count, page, page_size,
        total_pages, has_more, statistics, sql_hash
        """
        from services.sql_generator import validate_sql, fix_table_names
        from utils.json_encoder import safe_json_dumps

        sql_fixed = fix_table_names(sql).rstrip(';').strip()

        is_valid, error_msg = validate_sql(sql_fixed)
        if not is_valid:
            return json.dumps({"success": False, "error": f"SQL 验证失败: {error_msg}", "sql": sql_fixed}, ensure_ascii=False)

        try:
            # 先查总数
            count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql_fixed}) AS _sub"
            def _sync_count():
                r = db.execute(text(count_sql))
                return r.fetchone()[0]
            total_count = await asyncio.to_thread(_sync_count)

            # 分页查询
            offset = (page - 1) * page_size
            paginated_sql = f"{sql_fixed} LIMIT {page_size} OFFSET {offset}"

            def _sync_execute():
                r = db.execute(text(paginated_sql))
                rows = r.fetchall()
                return [dict(zip(r.keys(), row)) for row in rows] if rows else []

            rows = await asyncio.to_thread(_sync_execute)

            columns = list(rows[0].keys()) if rows else []
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            sql_hash = _cache_sql(sql_fixed)

            stats = _compute_statistics(rows)

            result = {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_more": page < total_pages,
                "statistics": stats,
                "sql_hash": sql_hash,
            }

            result_store["sql"] = sql_fixed
            result_store["sql_hash"] = sql_hash
            result_store["query_result"] = result

            logger.info(f"execute_sql 完成: {total_count} 条, {total_pages} 页")
            return safe_json_dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"execute_sql 失败: {e}")
            return json.dumps({"success": False, "error": str(e), "sql": sql_fixed}, ensure_ascii=False)

    @tool
    async def analyze_data(data_json: str, question: str) -> str:
        """
        对 SQL 查询结果进行数据分析。
        data_json: execute_sql 返回的完整 JSON 字符串
        question: 分析角度或用户原始问题
        返回: 结构化分析 JSON (AnalysisOutput)
        """
        analysis_llm = _create_llm(temperature=0.3)

        prompt = f"""你是一个数据分析专家。请对以下查询结果进行分析。

用户问题：{question}

查询结果数据（JSON）：
{data_json}

请输出结构化分析：
1. summary: 用 2-4 句话总结数据特征
2. key_findings: 3-5 条关键发现
3. statistics: 提取关键数值（平均值、最高、最低、趋势等）
4. chart_suggestion: 如果数据适合图表展示，推荐图表类型（bar/line/pie/scatter）、标题（≤15字）和理由

只输出 JSON，不要有任何额外文字。"""

        try:
            structured_llm = analysis_llm.with_structured_output(AnalysisOutput)
            analysis: AnalysisOutput = await structured_llm.ainvoke(prompt)

            result_store["analysis_result"] = analysis.model_dump()

            logger.info(f"analyze_data 完成: chart={analysis.chart_suggestion.type if analysis.chart_suggestion else 'none'}")
            return json.dumps(analysis.model_dump(), ensure_ascii=False)

        except Exception as e:
            logger.warning(f"with_structured_output 失败 ({e})，回退到 JSON 解析")

            resp = await analysis_llm.ainvoke(prompt + "\n\n请严格按以下 JSON 格式输出：\n"
                "{\"summary\":\"...\", \"key_findings\":[\"...\"], \"statistics\":{...}, "
                "\"chart_suggestion\":{\"type\":\"bar\", \"title\":\"...\", \"reason\":\"...\"} or null}")

            try:
                content = resp.content.strip()
                content = content.removeprefix("```json").removesuffix("```").strip()
                data = json.loads(content)
                result_store["analysis_result"] = data
                return json.dumps(data, ensure_ascii=False)
            except Exception:
                return json.dumps({"error": "分析失败", "raw": resp.content[:500]}, ensure_ascii=False)

    return [generate_sql, execute_sql, analyze_data]
