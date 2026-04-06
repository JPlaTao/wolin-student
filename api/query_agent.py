import os
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import text

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings

from database import get_db

load_dotenv()

router = APIRouter(prefix="/query", tags=["自然语言查询"])

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 加载向量知识库
vectordb = None
try:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if api_key:
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=api_key
        )
        if os.path.exists("./chroma_db"):
            vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            print("向量知识库加载成功")
except Exception as e:
    print(f"向量知识库加载失败: {e}")


class QueryRequest(BaseModel):
    question: str


# 全局记忆（修复：每次只保留最新10轮，防止过长报错）
memory = []

SCHEMA_DESC = """
数据库表结构：
1. teacher (教师表)
   - teacher_id INT 主键
   - teacher_name VARCHAR
   - gender VARCHAR
   - phone VARCHAR
   - role VARCHAR (counselor/headteacher/lecturer)
   - is_deleted BOOLEAN (0=未删除)

2. class (班级表)
   - class_id INT 主键
   - class_name VARCHAR
   - start_time DATETIME
   - head_teacher_id INT 外键 -> teacher.teacher_id
   - is_deleted BOOLEAN

3. stu_basic_info (学生表)
   - stu_id INT 主键
   - stu_name VARCHAR
   - native_place, graduated_school, major, admission_date, graduation_date, education, age, gender
   - advisor_id INT 外键 -> teacher.teacher_id
   - class_id INT 外键 -> class.class_id
   - is_deleted BOOLEAN

4. stu_exam_record (成绩表)
   - stu_id INT 外键 -> stu_basic_info.stu_id
   - seq_no INT (考核序次)
   - grade INT (0-100)
   - exam_date DATE
   - is_deleted INT (0=未删除, 1=已删除)

5. employment (就业表)
   - emp_id INT 主键
   - stu_id INT 外键 -> stu_basic_info.stu_id
   - stu_name VARCHAR (冗余)
   - class_id INT
   - open_time DATE
   - offer_time DATE
   - company VARCHAR
   - salary FLOAT
   - is_deleted BOOLEAN

重要规则：
- 所有查询必须过滤 is_deleted = 0 或 False（根据字段类型）
- 成绩表的 is_deleted 是 INT，所以用 is_deleted = 0
- 只生成 SELECT 语句，禁止 UPDATE/DELETE/INSERT/DROP
- 表名和字段名使用反引号包裹
- 返回的列名使用英文别名，便于前端解析
"""


def classify_intent(question: str):
    knowledge_keywords = ["为什么", "什么原因", "解释", "说明", "含义", "规则", "定义", "不准", "误差", "限制", "注意"]
    if any(kw in question for kw in knowledge_keywords):
        return "knowledge"
    sql_keywords = ["查询", "多少", "几个", "平均", "最高", "最低", "排名", "列表", "统计", "每个", "各个", "薪资",
                    "年龄", "成绩", "学生", "班级", "老师", "就业", "考试"]
    if any(kw in question for kw in sql_keywords):
        return "sql"
    return "chat"


def generate_sql(question, retry=False):
    system_msg = "你是一个MySQL专家，只输出SQL语句，不要有任何额外解释。以分号结尾。"
    if retry:
        system_msg += " 上一次生成的SQL执行失败，请修正。只输出修正后的SQL语句。"

    # 构建消息（不使用全局 memory，避免重复叠加爆炸）
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"根据以下数据库结构：\n{SCHEMA_DESC}\n\n用户问题：{question}\n请输出SQL语句："}
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.1,
    )
    sql = response.choices[0].message.content.strip()
    sql = re.sub(r'^```sql\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)
    return sql


@router.post("/natural")
def natural_query(req: QueryRequest, db: Session = Depends(get_db)):
    question = req.question
    intent = classify_intent(question)

    # ===================== 知识库问答 =====================
    if intent == "knowledge":
        context = ""
        if vectordb:
            try:
                docs = vectordb.similarity_search(question, k=3)
                context = "\n\n".join([doc.page_content for doc in docs])
            except:
                pass

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你必须只根据文档内容回答，无答案则回复：无法回答该问题。"
                },
                {
                    "role": "user",
                    "content": f"文档：\n{context}\n\n问题：{question}"
                }
            ]
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.1
            )
            answer = response.choices[0].message.content
            return {"type": "answer", "question": question, "answer": answer}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 失败: {str(e)}")

    # ===================== SQL 查询 =====================
    elif intent == "sql":
        try:
            sql = generate_sql(question, retry=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"生成SQL失败: {str(e)}")

        if not sql.strip().lower().startswith("select"):
            raise HTTPException(status_code=400, detail="仅支持 SELECT 查询")

        try:
            res = db.execute(text(sql))
            rows = res.fetchall()
            cols = res.keys()
            data = [dict(zip(cols, r)) for r in rows]
            return {
                "type": "sql",
                "question": question,
                "sql": sql,
                "data": data,
                "count": len(data)
            }
        except Exception as e:
            try:
                sql2 = generate_sql(question, retry=True)
                res = db.execute(text(sql2))
                rows = res.fetchall()
                cols = res.keys()
                data = [dict(zip(cols, r)) for r in rows]
                return {
                    "type": "sql",
                    "question": question,
                    "sql": sql2,
                    "data": data,
                    "count": len(data)
                }
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"SQL错误: {str(e2)}")

    # ===================== 普通闲聊 =====================
    else:
        try:
            messages = [
                {"role": "system", "content": "你是友好助手，简洁自然回答。"},
                {"role": "user", "content": question}
            ]
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7
            )
            answer = response.choices[0].message.content
            return {"type": "answer", "question": question, "answer": answer}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI失败: {str(e)}")
