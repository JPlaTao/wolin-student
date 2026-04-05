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

# 加载向量知识库（如果存在）
vectordb = None
try:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("警告: 未设置 DASHSCOPE_API_KEY，知识库功能不可用")
    else:
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=api_key
        )
        if os.path.exists("./chroma_db") and os.path.isdir("./chroma_db"):
            vectordb = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
            print("向量知识库加载成功")
        else:
            print("知识库目录不存在，请先运行 build_knowledge_base() 构建")
except Exception as e:
    print(f"向量知识库加载失败: {e}")

class QueryRequest(BaseModel):
    question: str

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

常见问题示例：
- 问：老师有多少人？ 答：SELECT COUNT(*) AS count FROM teacher WHERE is_deleted = 0;
- 问：学生总数？ 答：SELECT COUNT(*) AS total FROM stu_basic_info WHERE is_deleted = 0;
- 问：每个班级的平均分？ 答：SELECT c.class_name, AVG(e.grade) AS avg_grade FROM class c JOIN stu_basic_info s ON c.class_id = s.class_id JOIN stu_exam_record e ON s.stu_id = e.stu_id WHERE c.is_deleted = 0 AND s.is_deleted = 0 AND e.is_deleted = 0 GROUP BY c.class_id;
- 问：年龄最大的学生？ 答：SELECT stu_name, age FROM stu_basic_info WHERE is_deleted = 0 ORDER BY age DESC LIMIT 1;
- 问：薪资最高的前五名学生？ 答：SELECT stu_name, salary FROM employment WHERE is_deleted = 0 ORDER BY salary DESC LIMIT 5;
"""

def classify_intent(question: str):
    knowledge_keywords = ["为什么", "什么原因", "解释", "说明", "含义", "规则", "定义", "不准", "误差", "限制", "注意"]
    if any(kw in question for kw in knowledge_keywords):
        return "knowledge"
    sql_keywords = ["查询", "多少", "几个", "平均", "最高", "最低", "排名", "列表", "统计", "每个", "各个", "薪资", "年龄", "成绩", "学生", "班级", "老师", "就业", "考试"]
    if any(kw in question for kw in sql_keywords):
        return "sql"
    return "chat"

def generate_sql(question, retry=False):
    system_msg = "你是一个MySQL专家，只输出SQL语句，不要有任何额外解释。以分号结尾。"
    if retry:
        system_msg += " 上一次生成的SQL执行失败，请修正。只输出修正后的SQL语句。"
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"根据以下数据库结构：\n{SCHEMA_DESC}\n\n用户问题：{question}\n请输出SQL语句："}
        ],
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

    # 1. 知识库问题（优先使用向量检索）
    if intent == "knowledge":
        context = ""
        if vectordb is not None:
            try:
                docs = vectordb.similarity_search(question, k=3)
                context = "\n\n".join([doc.page_content for doc in docs])
                print(f"向量检索到 {len(docs)} 个片段")
            except Exception as e:
                print(f"向量检索失败: {e}")
        else:
            # 回退：直接读取文档内容
            docs_content = ""
            docs_dir = "docs"
            if os.path.exists(docs_dir):
                for filename in os.listdir(docs_dir):
                    if filename.endswith(".md") or filename.endswith(".txt"):
                        filepath = os.path.join(docs_dir, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                docs_content += f.read() + "\n\n"
                        except Exception as e:
                            print(f"读取 {filename} 失败: {e}")
            context = docs_content[:20000] if docs_content else "暂无文档。"

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个严格基于文档的问答助手。你必须只根据下面「文档内容」中的信息回答用户问题。如果文档内容中没有明确的答案，请直接回复「根据现有文档，无法回答该问题」。不要使用你自己的知识补充任何内容。"},
                    {"role": "user", "content": f"文档内容：\n{context}\n\n用户问题：{question}"}
                ],
                temperature=0.1,
            )
            answer = response.choices[0].message.content
            return {"type": "answer", "question": question, "answer": answer}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")

    # 2. SQL 数据查询
    elif intent == "sql":
        try:
            sql = generate_sql(question, retry=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 生成 SQL 失败: {str(e)}")
        if not sql.strip().lower().startswith("select"):
            raise HTTPException(status_code=400, detail="只能生成 SELECT 查询")
        try:
            result = db.execute(text(sql))
            rows = result.fetchall()
            columns = result.keys()
            data = [dict(zip(columns, row)) for row in rows]
            return {"type": "sql", "question": question, "sql": sql, "data": data, "count": len(data)}
        except Exception as e:
            try:
                sql_corrected = generate_sql(question, retry=True)
                if not sql_corrected.strip().lower().startswith("select"):
                    raise HTTPException(status_code=400, detail="修正后的 SQL 仍然不是 SELECT 语句")
                result = db.execute(text(sql_corrected))
                rows = result.fetchall()
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in rows]
                return {"type": "sql", "question": question, "sql": sql_corrected, "data": data, "count": len(data)}
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"SQL 执行失败: {str(e)}\n原始 SQL: {sql}\n修正后 SQL: {sql_corrected}")

    # 3. 闲聊/通用对话
    else:
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个友好的助手，可以和学生管理系统相关的用户闲聊。回答要简洁、自然、有趣。"},
                    {"role": "user", "content": question}
                ],
                temperature=0.7,
            )
            answer = response.choices[0].message.content
            return {"type": "answer", "question": question, "answer": answer}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI 回答失败: {str(e)}")