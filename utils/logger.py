import logging
import os
import re
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

# ANSI 颜色常量
_RESET = '\033[0m'
_CYAN = '\033[36m'
_GREEN = '\033[32m'
_YELLOW = '\033[33m'
_RED = '\033[31m'
_BOLD_CYAN = '\033[1;36m'
_RED_BG = '\033[41m'

_LEVEL_COLORS = {
    'DEBUG': _CYAN,
    'INFO': _GREEN,
    'WARNING': _YELLOW,
    'ERROR': _RED,
    'CRITICAL': _RED_BG,
}


class ConsoleFormatter(logging.Formatter):
    """控制台格式化器，逐字段染色，不污染整行"""

    def format(self, record):
        # 时间戳
        record.asctime = self.formatTime(record, '%Y-%m-%d %H:%M:%S')

        # 级别名 — 单独染色，其余字段用终端默认色
        lc = _LEVEL_COLORS.get(record.levelname, '')
        colored_level = f'{lc}{record.levelname:<8s}{_RESET}'

        # 消息体 — 内部分段染色
        msg = record.getMessage()

        # HTTP 方法 → 按语义染色
        def _color_method(m):
            color = {
                'GET': _CYAN,
                'POST': _GREEN,
                'PUT': _YELLOW,
                'PATCH': _YELLOW,
                'DELETE': _RED,
            }.get(m.group(1), '')
            return f'{color}{m.group(1)}{_RESET}'
        msg = re.sub(r'\b(GET|POST|PUT|PATCH|DELETE)\b', _color_method, msg)

        def _color_status(m):
            code = int(m.group(1))
            if 200 <= code < 300:
                return f'→ {_GREEN}{m.group(1)}{_RESET}'
            elif 300 <= code < 400:
                return f'→ {_YELLOW}{m.group(1)}{_RESET}'
            else:
                return f'→ {_RED}{m.group(1)}{_RESET}'
        msg = re.sub(r'→ (\d{3})', _color_status, msg)

        # 异常堆栈
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        exc = f'\n{record.exc_text}' if record.exc_text else ''

        return f'{record.asctime} {colored_level} {msg}{exc}'


def setup_logger(
    name: str = "wolin_student",
    log_level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    配置并返回日志记录器

    Args:
        name: 日志记录器名称
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件存储目录
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量

    Returns:
        配置好的日志记录器
    """
    # 关闭 uvicorn 自带的 access log（使用自定义 middleware 代替）
    # 放在 early return 之前以确保每次调用都执行
    _uvicorn_access = logging.getLogger("uvicorn.access")
    _uvicorn_access.setLevel(logging.WARNING)
    _uvicorn_access.handlers.clear()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 如果已经配置过处理器，直接返回
    if logger.handlers:
        return logger

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器 — 逐字段彩色输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ConsoleFormatter(datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(console_handler)

    # 文件处理器 - 按大小轮转
    log_file = log_path / "app.log"
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 错误日志单独存储
    error_log_file = log_path / "error.log"
    error_handler = RotatingFileHandler(
        filename=error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 审计日志 — 敏感操作专用
    audit_log_file = log_path / "audit.log"
    audit_handler = RotatingFileHandler(
        filename=audit_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    audit_handler.setLevel(logging.WARNING)
    audit_handler.setFormatter(formatter)
    audit_handler.addFilter(SensitiveOperationFilter(allow_sensitive=True))
    logger.addHandler(audit_handler)

    # app.log 排除敏感操作（避免重复写入）
    # file_handler 在 audit_handler 之后添加过滤器
    file_handler.addFilter(SensitiveOperationFilter(allow_sensitive=False))

    return logger


class SensitiveOperationFilter(logging.Filter):
    """只允许（或排除）敏感操作日志的记录过滤器"""

    def __init__(self, allow_sensitive: bool = True):
        super().__init__()
        self.allow_sensitive = allow_sensitive

    def filter(self, record: logging.LogRecord) -> bool:
        is_sensitive = getattr(record, 'operation_type', None) == 'sensitive'
        return is_sensitive if self.allow_sensitive else not is_sensitive


# 创建全局日志记录器实例
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器实例

    Args:
        name: 模块名称，如果为None则返回根日志记录器

    Returns:
        日志记录器
    """
    if name:
        return logging.getLogger(f"wolin_student.{name}")
    return logger
