"""Prompt 模板文件加载器"""
import os

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt(name: str) -> str:
    """从 prompts/ 目录加载 prompt 模板文件"""
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()
