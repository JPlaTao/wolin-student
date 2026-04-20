"""
邮件发送 API
"""
from fastapi import APIRouter

from schemas.email_schemas import EmailSendRequest, EmailSendResponse
from services.email_service import get_email_service
from utils.logger import get_logger

router = APIRouter(prefix="/api/email", tags=["邮件"])
logger = get_logger("email_api")


@router.post("/send", response_model=EmailSendResponse)
async def send_email(request: EmailSendRequest):
    """
    发送邮件

    支持使用配置中的默认发件人，也支持在请求中指定发送者信息。

    - 不指定发送者信息：使用 config.json 中的默认配置
    - 指定发送者信息：使用请求中的配置（适合个人对个人发邮件）

    常用 SMTP 服务器：
    - QQ邮箱: smtp.qq.com:587
    - 163邮箱: smtp.163.com:587
    """
    email_service = get_email_service()

    result = email_service.send_email(
        to=request.to,
        subject=request.subject,
        content=request.content,
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        use_tls=request.use_tls,
        username=request.username,
        password=request.password,
        from_name=request.from_name
    )

    return EmailSendResponse(
        success=result["success"],
        to=result["to"],
        subject=result["subject"],
        sent_at=result["sent_at"]
    )
