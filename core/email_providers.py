"""
邮箱服务商配置
管理员可通过修改此配置来添加/更新支持的邮箱服务商
"""
from typing import Dict, Any

# 支持的邮箱服务商配置
# 管理员可在此处添加更多服务商
EMAIL_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "qq": {
        "name": "QQ邮箱",
        "smtp_host": "smtp.qq.com",
        "smtp_port": 465,
        "use_ssl": True,
        "default_from_name": "QQ邮件",
    },
    "163": {
        "name": "163邮箱",
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "use_ssl": True,
        "default_from_name": "网易邮件",
    },
    # 如需添加更多服务商，参照以下格式：
    # "gmail": {
    #     "name": "Gmail",
    #     "smtp_host": "smtp.gmail.com",
    #     "smtp_port": 587,
    #     "use_ssl": False,  # Gmail 使用 STARTTLS
    #     "default_from_name": "Gmail",
    # },
}


def get_provider_config(provider: str) -> Dict[str, Any]:
    """获取指定服务商配置"""
    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"不支持的邮箱服务商: {provider}")
    return EMAIL_PROVIDERS[provider]


def get_all_providers() -> list:
    """获取所有支持的服务商列表（供前端下拉选择）"""
    return [
        {"value": key, "label": config["name"]}
        for key, config in EMAIL_PROVIDERS.items()
    ]
