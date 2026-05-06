"""意图分类与 SQL 引用检测"""
import re
from typing import Optional, List, Any

from services.llm_service import get_llm_client, get_llm_temperature, get_llm_model
from utils.logger import get_logger

logger = get_logger("intent_classifier")

# ---------- Prompt 模板 ----------
INTENT_CLASSIFICATION_PROMPT = (
    "你是一个意图分类助手。根据对话历史和当前用户问题，判断用户意图。\n\n"
    "历史对话（最近5轮）：\n{history}\n\n"
    "当前问题：{question}\n\n"
    "意图选项（只输出一个单词）：\n"
    "- sql: 用户需要从数据库查询具体数据（如\"查询成绩\"、\"统计人数\"、\"列出学生\"）\n"
    "- analysis: 用户希望进行数据分析、解释原因、对比趋势（如\"为什么成绩低\"、\"分析就业率变化\"）\n"
    "- chat: 其他日常闲聊、问候、无关问题\n\n"
    "意图："
)

SQL_REFERENCE_CHECK_PROMPT = (
    "你是一个判断助手。根据对话历史和当前问题，判断用户是否想要"
    "**基于上一轮查询结果**进行新的查询。\n"
    "上一轮查询可能提供了一些过滤条件（如班级名称、时间范围等），用户可能希望复用这些条件。\n\n"
    "对话历史（最近2轮）：\n{history}\n\n"
    "当前问题：{question}\n\n"
    "判断规则：\n"
    "- 如果用户明确提到\"刚才\"、\"上一轮\"、\"再查一下\"、\"同样的\"、\"也\"、"
    "\"那个\"、\"再次\"、\"同样\"等词，或者明显引用上一轮的结果"
    "（如\"那个班的就业率\"），返回 \"YES\"。\n"
    "- 否则返回 \"NO\"。\n\n"
    "只输出 YES 或 NO。"
)


def sanitize_prompt_input(text: str) -> str:
    """
    清洗用户输入，防止 prompt 注入攻击。
    通过过滤常见的注入模式来防御此类攻击。
    """
    if not text:
        return ""

    injection_patterns = [
        r'(?i)(ignore\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(disregard\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(forget\s+(all\s+)?(previous|above|instruct))',
        r'(?i)(you\s+are\s+no\s+longer)',
        r'(?i)(you\s+are\s+now\s+a)',
        r'(?i)(pretend\s+you\s+are)',
        r'(?i)(act\s+as\s+if\s+you\s+are)',
        r'(?i)(new\s+system\s+prompt)',
        r'(?i)(override\s+(your\s+)?system)',
        r'(?i)(enable\s+(developer|admin|superuser)\s+mode)',
        r'(?i)(DAN\s+mode)',
        r'(?i)(jailbreak)',
        r'<system>',
        r'</system>',
        r'<system_prompt>',
        r'</system_prompt>',
        r'<instruction>',
        r'</instruction>',
        r'<\|.*?\|>',
        r'```\s*(system|instruction|prompt)',
        r'```\s*ignore',
        r'```\s*disregard',
    ]

    result = text
    for pattern in injection_patterns:
        result = re.sub(pattern, '[filtered]', result, flags=re.IGNORECASE)
    return result


async def classify_intent_llm(question: str, history_text: str = "") -> str:
    """使用 LLM 进行意图分类"""
    question_safe = sanitize_prompt_input(question)
    history_safe = sanitize_prompt_input(history_text)

    if history_safe:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(history=history_safe, question=question_safe)
    else:
        prompt = f"意图选项：sql / analysis / chat\n用户问题：{question_safe}\n意图："

    client = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
            max_tokens=10,
        )
        intent = resp.choices[0].message.content.strip().lower()
        if intent in ("sql", "analysis", "chat"):
            return intent
    except Exception as e:
        logger.warning(f"LLM意图分类失败: {e}，降级到关键词匹配")

    # 降级关键词
    knowledge_keywords = [
        "为什么", "什么原因", "解释", "说明", "含义", "规则",
        "定义", "分析", "分布", "趋势", "对比",
    ]
    if any(kw in question for kw in knowledge_keywords):
        return "analysis"
    sql_keywords = [
        "查询", "多少", "几个", "平均", "最高", "最低", "排名",
        "列表", "统计", "每个", "各个", "薪资", "年龄", "成绩",
        "学生", "班级", "老师", "就业", "考试",
    ]
    if any(kw in question for kw in sql_keywords):
        return "sql"
    return "chat"


async def check_sql_reference(question: str, history_text: str) -> str:
    """检测用户是否需要引用上一轮的 SQL 查询"""
    question_safe = sanitize_prompt_input(question)
    history_safe = sanitize_prompt_input(history_text)
    prompt = SQL_REFERENCE_CHECK_PROMPT.format(history=history_safe, question=question_safe)

    client = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=get_llm_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=get_llm_temperature(),
            max_tokens=10,
        )
        result = resp.choices[0].message.content.strip().upper()
        if result in ("YES", "NO"):
            return result
    except Exception as e:
        logger.error(f"SQL引用检测失败: {e}")

    # 降级关键词
    reference_keywords = [
        "刚才", "上一轮", "再查", "同样的", "也", "那个",
        "再次", "同样", "这个班", "那个班",
    ]
    if any(kw in question for kw in reference_keywords):
        return "YES"
    return "NO"
