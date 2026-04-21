"""
邮件相关的数据模型
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class EmailSendRequest(BaseModel):
    """发送邮件请求（简化版）"""
    to: List[str] = Field(..., description="收件人列表", min_length=1)
    subject: str = Field(..., min_length=1, max_length=200, description="邮件主题")
    content: str = Field(..., min_length=1, description="邮件内容")

    @field_validator("to")
    @classmethod
    def validate_emails(cls, v):
        for email in v:
            if "@" not in email or "." not in email:
                raise ValueError(f"无效的邮箱地址: {email}")
        return v


class EmailSendResponse(BaseModel):
    """发送邮件响应"""
    success: bool
    to: List[str]
    subject: str
    sent_at: str
    message: str = "发送成功"


class EmailConfigRequest(BaseModel):
    """配置用户邮箱请求"""
    provider: str = Field(..., description="邮箱服务商: qq, 163")
    email_address: str = Field(..., description="邮箱地址")
    auth_code: str = Field(..., description="授权码")
    from_name: str = Field(None, description="发件人昵称")


class EmailConfigResponse(BaseModel):
    """邮箱配置响应"""
    provider: str
    email_address: str
    from_name: Optional[str] = None
    has_auth_code: bool  # 是否已配置授权码（不返回实际授权码）


class EmailProviderInfo(BaseModel):
    """邮箱服务商信息"""
    value: str
    label: str


class EmailProvidersResponse(BaseModel):
    """支持的服务商列表响应"""
    providers: List[EmailProviderInfo]
