"""流式输出缓冲区管理器"""

import datetime as dt_module


class StreamBuffer:
    """流式输出缓冲区管理器"""

    def __init__(self, min_chunk_size: int = 5, max_wait_ms: int = 50):
        """
        参数:
            min_chunk_size: 最小累积字符数才发送一次
            max_wait_ms: 最大等待毫秒数，即使未达到最小字符数也发送
        """
        self.min_chunk_size = min_chunk_size
        self.max_wait_ms = max_wait_ms
        self.buffer = ""
        self.last_send_time = dt_module.datetime.now()

    def add(self, text: str) -> list[str]:
        """添加文本，返回可发送的 chunks"""
        self.buffer += text
        chunks = []
        now = dt_module.datetime.now()
        elapsed = (now - self.last_send_time).total_seconds() * 1000

        if len(self.buffer) >= self.min_chunk_size or elapsed >= self.max_wait_ms:
            if self.buffer:
                chunks.append(self.buffer)
                self.buffer = ""
                self.last_send_time = now

        return chunks

    def flush(self) -> str:
        """强制刷新缓冲区，返回剩余内容"""
        result = self.buffer
        self.buffer = ""
        self.last_send_time = dt_module.datetime.now()
        return result
