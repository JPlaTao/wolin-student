"""LLM 客户端初始化与管理（延迟加载，避免 import 时执行网络 IO）"""
from openai import AsyncOpenAI
from core.settings import get_settings
from utils.logger import get_logger

logger = get_logger("llm_service")

_client = None
_config = {}


def _initialize():
    """延迟初始化 LLM 客户端和配置"""
    global _client, _config
    settings = get_settings()
    provider = settings.llm.provider.lower()

    api_key = _resolve_api_key(provider, settings)
    _client = AsyncOpenAI(
        api_key=api_key,
        base_url=settings.llm.base_url
    )
    _config = {
        "temperature": settings.llm.effective_temperature,
        "model": settings.llm.model,
        "provider": provider,
    }
    logger.info(f"LLM 客户端初始化完成: provider={provider}, model={settings.llm.model}")


def _resolve_api_key(provider: str, settings) -> str:
    """根据 provider 解析对应的 API key"""
    key_map = {
        "kimi": settings.api_keys.kimi,
        "deepseek": settings.api_keys.deepseek,
        "openai": settings.api_keys.openai,
    }
    if provider in key_map:
        return key_map[provider]
    logger.warning(f"未知 LLM provider: {provider}，尝试使用 kimi key")
    return settings.api_keys.kimi


def get_llm_client() -> AsyncOpenAI:
    """获取 LLM 客户端（首次调用时初始化）"""
    if _client is None:
        _initialize()
    return _client


def get_llm_temperature() -> float:
    """获取 LLM 温度参数"""
    if not _config:
        _initialize()
    return _config["temperature"]


def get_llm_model() -> str:
    """获取当前 LLM 模型名"""
    if not _config:
        _initialize()
    return _config["model"]


def get_llm_provider() -> str:
    """获取当前 LLM 提供商"""
    if not _config:
        _initialize()
    return _config["provider"]
