"""
邮件相关的数据模型
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class EmailSendRequest(BaseModel):
    """发送邮件请求"""
    to: List[str] = Field(..., description="收件人列表", min_length=1)
    subject: str = Field(..., min_length=1, max_length=200, description="邮件主题")
    content: str = Field(..., min_length=1, description="邮件内容")

    # SMTP 配置（可选，不填则使用 config.json 默认值）
    smtp_host: Optional[str] = Field(None, description="SMTP服务器地址，如 smtp.qq.com")
    smtp_port: Optional[int] = Field(None, ge=1, le=65535, description="SMTP端口，默认587")
    use_tls: Optional[bool] = Field(None, description="是否使用TLS加密，默认True")
    username: Optional[str] = Field(None, description="发件人邮箱")
    password: Optional[str] = Field(None, description="发件人邮箱授权码")
    from_name: Optional[str] = Field(None, description="发件人名称")

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
