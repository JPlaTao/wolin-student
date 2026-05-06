"""安全的 JSON 编码器，自动处理所有不可序列化的类型。"""
import json
import uuid
import decimal
import datetime as dt_module
from enum import Enum
from typing import Any


class SafeJSONEncoder(json.JSONEncoder):
    """安全的 JSON 编码器，自动处理所有不可序列化的类型。"""

    def default(self, obj):
        if isinstance(obj, (dt_module.datetime, dt_module.date, dt_module.time)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except Exception:
                return obj.hex()
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        try:
            return str(obj)
        except Exception:
            return f"<unserializable: {type(obj).__name__}>"


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """安全的 JSON 序列化函数，自动处理不可序列化类型。"""
    return json.dumps(obj, cls=SafeJSONEncoder, **kwargs)
