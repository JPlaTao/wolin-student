import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from dotenv import load_dotenv

load_dotenv()

def build_knowledge_base(docs_dir="docs", persist_dir="./chroma_db"):
    if os.path.exists(persist_dir) and os.path.isdir(persist_dir) and os.listdir(persist_dir):
        print(f"知识库已存在: {persist_dir}，跳过构建。")
        return True

    print("开始构建知识库...")
    documents = []
    if not os.path.isdir(docs_dir):
        print(f"错误: 目录 {docs_dir} 不存在，无法构建知识库。")
        return False

    for filename in os.listdir(docs_dir):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(docs_dir, filename)
            try:
                loader = TextLoader(filepath, encoding="utf-8")
                docs = loader.load()
                documents.extend(docs)
                print(f"已加载: {filename}")
            except Exception as e:
                print(f"加载 {filename} 失败: {e}")

    if not documents:
        print("没有找到任何文档，请检查 docs/ 目录。")
        return False

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)
    print(f"文档已分割为 {len(chunks)} 个文本块")

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("错误: 未找到 DASHSCOPE_API_KEY 环境变量，请在 .env 文件中设置")
        return False

    embeddings = DashScopeEmbeddings(
        model="text-embedding-v3",
        dashscope_api_key=api_key
    )

    # 新版 langchain-chroma 会自动持久化，无需调用 .persist()
    Chroma.from_documents(chunks, embeddings, persist_directory=persist_dir)
    print(f"知识库构建完成，保存在 {persist_dir}")
    return True