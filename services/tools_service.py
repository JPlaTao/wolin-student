"""教师工具业务逻辑层 — LLM 调用 + Prompt 构建"""
from sqlalchemy.orm import Session

from services.llm_service import get_llm_client, get_llm_model, get_llm_temperature
from dao import exam_dao
from core.exceptions import NotFoundException
from utils.logger import get_logger

logger = get_logger("tools_service")

# ── Prompt 模板 ──────────────────────────────────────────────

STYLE_MAP = {
    "formal": "风格要求：正式、规范、书面化。",
    "humorous": "风格要求：幽默、轻松、有创意，可以适当用梗。",
    "warm": "风格要求：亲切、温和、口语化，像朋友间说话。",
}

POLISH_SYSTEM_PROMPT = (
    "你是学校行政秘书。请将用户输入的草稿改写为一份{style}的通知。\n"
    "{style_map}\n"
    "要求：格式规范，语气得体，重点突出，包含标题、正文、落款。"
)

DIAGNOSE_SYSTEM_PROMPT = (
    "你是一位数据分析师兼班主任。分析用户提供的学生成绩列表"
    "（按时间顺序，seq_no 表示第几次考试）。\n"
    "1. 指出哪科进步最大；\n"
    "2. 指出哪科退步明显；\n"
    "3. 给出一句针对性的鼓励建议。\n\n"
    "注意：\n"
    "- 当前只有一个科目的成绩（grade 字段），所以主要分析成绩的趋势变化\n"
    "- 用数字说话（进步/退步了多少分）\n"
    "- 语气要温和、有建设性"
)

COMMENT_SYSTEM_PROMPT = (
    "你是一位拥有20年经验的资深班主任。请根据用户提供的学生特点关键词，"
    "写一段100字左右的期末评语。\n\n"
    "要求：\n"
    "1. 语气亲切，使用'三明治沟通法'（先表扬优点，再委婉提出缺点，最后给予期望）\n"
    "2. 多用成语\n"
    "3. 避免'希望你以后...'这类死板句式\n"
    "4. 评语要具体，能看出是针对该生特点写的，而不是通用模板"
)


# ── 工具函数 ──────────────────────────────────────────────────


async def _call_llm(system_prompt: str, user_content: str, temperature: float = None) -> str:
    """调用 LLM 并返回生成的文本。"""
    client = get_llm_client()
    model = get_llm_model()
    if temperature is None:
        temperature = get_llm_temperature()

    resp = await client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return resp.choices[0].message.content


# ── 公开 API ──────────────────────────────────────────────────


async def polish_notice(text: str, style: str = "formal") -> str:
    """公告/通知润色"""
    style_desc = STYLE_MAP.get(style, STYLE_MAP["formal"])
    system_prompt = POLISH_SYSTEM_PROMPT.format(style=style, style_map=style_desc)
    logger.info(f"公告润色: style={style}, text_len={len(text)}")
    return await _call_llm(system_prompt, text)


async def diagnose_score(stu_id: int, db: Session):
    """成绩波动诊断 — 从数据库拉取记录并交由 LLM 分析

    返回 (stu_name, class_name, exam_records, analysis_text)
    """
    result = exam_dao.exam_get(stu_id=stu_id, seq_no=None, db=db)

    if result["msg"] != "success" or not result.get("data"):
        raise NotFoundException(message="未找到该学生的成绩记录")

    data = result["data"]
    stu_name = data[0]["stu_name"]
    class_name = data[0]["class_name"]

    # 构建供 LLM 分析的文本
    records_lines = [f"学生：{stu_name}，班级：{class_name}\n"]
    for r in data:
        records_lines.append(
            f"第{r['seq_no']}次考试：{r['grade']}分，日期：{r['exam_date']}\n"
        )
    records_str = "".join(records_lines)

    # 同时返回结构化列表给前端渲染
    exam_records = [
        {"seq_no": r["seq_no"], "grade": float(r["grade"]), "exam_date": str(r["exam_date"])}
        for r in data
    ]

    logger.info(f"成绩诊断: stu_id={stu_id}, stu_name={stu_name}, records={len(data)}")
    analysis_text = await _call_llm(DIAGNOSE_SYSTEM_PROMPT, records_str)
    return stu_name, class_name, exam_records, analysis_text


async def generate_comment(keywords: str) -> str:
    """期末评语生成（温度 0.9 以保证创意性）"""
    logger.info(f"评语生成: keywords={keywords}")
    return await _call_llm(COMMENT_SYSTEM_PROMPT, keywords, temperature=0.9)
