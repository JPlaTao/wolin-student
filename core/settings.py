"""
配置管理模块
使用 Pydantic + JSON 配置文件，支持类型验证和自动补全
"""
import json
import os
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel, Field, field_validator, computed_field


class DatabaseConfig(BaseModel):
    """数据库配置"""
    # 连接参数（替代原来的 url）
    driver: str = Field(default="mysql+pymysql", description="数据库驱动")
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=3306, ge=1, le=65535, description="数据库端口")
    username: str = Field(default="root", description="数据库用户名")
    password: str = Field(default="", description="数据库密码")
    database: str = Field(..., description="数据库名")

    # 连接池配置
    pool_size: int = Field(default=5, ge=1, le=20, description="连接池大小")
    pool_recycle: int = Field(default=3600, ge=60, description="连接回收时间(秒)")

    @computed_field
    @property
    def url(self) -> str:
        """动态生成数据库连接 URL"""
        return f"{self.driver}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class JWTConfig(BaseModel):
    """JWT配置"""
    secret_key: str = Field(..., min_length=16, description="JWT密钥")
    algorithm: str = Field(default="HS256", description="加密算法")
    access_token_expire_minutes: int = Field(default=1440, ge=1, description="Token过期时间(分钟)")


class APIKeysConfig(BaseModel):
    """API密钥配置"""
    dashscope: str = Field(default="", description="阿里云 DashScope API 密钥")
    deepseek: str = Field(default="", description="DeepSeek API 密钥")
    openai: str = Field(default="", description="OpenAI API 密钥")
    kimi: str = Field(default="", description="Kimi (Moonshot) API 密钥")


class LLMConfig(BaseModel):
    """LLM 模型配置"""
    provider: str = Field(default="kimi", description="模型提供商: kimi, deepseek, openai")
    model: str = Field(default="kimi-k2.5", description="模型名称")
    base_url: str = Field(default="https://api.moonshot.cn/v1", description="API 基础URL")
    temperature: float = Field(default=0.7, ge=0, le=2, description="默认温度参数")
    max_tokens: int = Field(default=4096, ge=100, description="最大生成token数")

    # 仅支持 temperature=1 的模型列表（通常是 Reasoner/Actor 分离的 Agent 模型）
    _TEMPERATURE_ONE_MODELS = frozenset([
        "kimi-k2.5",
        "kimi-k1.5",
        "moonshot-v1-auto",
    ])

    @computed_field
    @property
    def effective_temperature(self) -> float:
        """
        获取有效的 temperature 值。

        部分模型（如 kimi-k2.5 等 Reasoner 模型）只支持 temperature=1，
        使用此属性可自动适配，避免手动处理。
        """
        model_lower = self.model.lower()
        if model_lower in self._TEMPERATURE_ONE_MODELS:
            return 1.0
        return self.temperature


class AppConfig(BaseModel):
    """应用配置"""
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8080, ge=1, le=65535, description="服务端口")
    debug: bool = Field(default=False, description="调试模式")
    title: str = Field(default="学生管理系统", description="应用标题")
    version: str = Field(default="1.0.0", description="版本号")


class Settings(BaseModel):
    """全局配置"""
    database: DatabaseConfig
    jwt: JWTConfig
    api_keys: APIKeysConfig
    llm: LLMConfig = Field(default_factory=LLMConfig)
    app: AppConfig


def _find_config_file() -> Path:
    """查找配置文件，支持从环境变量或默认路径"""
    # 优先使用环境变量指定的路径
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # 默认查找顺序
    search_paths = [
        Path("config.json"),
        Path(__file__).parent.parent / "config.json",
    ]

    for path in search_paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        "配置文件未找到！请创建 config.json 或设置 CONFIG_PATH 环境变量"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例（自动加载并缓存）
    首次调用时从 config.json 加载配置
    """
    config_path = _find_config_file()

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    return Settings(**config_data)


# 便捷访问函数
def reload_settings() -> Settings:
    """重新加载配置（清除缓存）"""
    get_settings.cache_clear()
    return get_settings()
