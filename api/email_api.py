"""
邮件发送 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.email_schemas import (
    EmailSendRequest, EmailSendResponse,
    EmailConfigRequest, EmailConfigResponse,
    EmailProvidersResponse, EmailProviderInfo
)
from services.email_service import get_email_service
from core.email_providers import get_all_providers, get_provider_config
from core.database import get_db
from core.auth import get_current_user
from utils.logger import get_logger

router = APIRouter(prefix="/api/email", tags=["邮件"])
logger = get_logger("email_api")


@router.get("/providers", response_model=EmailProvidersResponse)
async def get_providers():
    """获取支持的邮箱服务商列表"""
    providers = get_all_providers()
    return EmailProvidersResponse(providers=providers)


@router.get("/config", response_model=EmailConfigResponse)
async def get_email_config(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前用户的邮箱配置"""
    if not current_user.email_provider or not current_user.email_address:
        raise HTTPException(status_code=404, detail="未配置邮箱，请先配置")

    return EmailConfigResponse(
        provider=current_user.email_provider,
        email_address=current_user.email_address,
        from_name=current_user.email_from_name,
        has_auth_code=bool(current_user.email_auth_code)
    )


@router.post("/config", response_model=EmailConfigResponse)
async def configure_email(
    request: EmailConfigRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """配置/更新用户邮箱"""
    # 验证服务商是否有效
    try:
        get_provider_config(request.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail="不支持的邮箱服务商")

    # 验证邮箱域名与服务商匹配
    provider_config = get_provider_config(request.provider)
    smtp_domain = provider_config["smtp_host"].replace("smtp.", "")
    email_domain = request.email_address.split("@")[1] if "@" in request.email_address else ""

    if email_domain != smtp_domain:
        raise HTTPException(
            status_code=400,
            detail=f"邮箱域名与服务商不匹配。使用 {provider_config['name']} 请填写真实的 {smtp_domain} 邮箱"
        )

    # 保存到用户表
    current_user.email_provider = request.provider
    current_user.email_address = request.email_address
    current_user.email_auth_code = request.auth_code
    current_user.email_from_name = request.from_name if request.from_name else provider_config["name"]
    db.commit()

    logger.info(f"[邮箱配置] 用户 {current_user.username} 配置了邮箱: {request.email_address}")

    return EmailConfigResponse(
        provider=current_user.email_provider,
        email_address=current_user.email_address,
        from_name=current_user.email_from_name,
        has_auth_code=True
    )


@router.post("/send", response_model=EmailSendResponse)
async def send_email(
    request: EmailSendRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发送邮件（使用用户已配置的邮箱）"""
    # 检查用户是否已配置邮箱
    if not current_user.email_provider or not current_user.email_address or not current_user.email_auth_code:
        raise HTTPException(
            status_code=400,
            detail="请先配置发件邮箱再发送邮件"
        )

    email_service = get_email_service()

    # 使用用户自定义昵称或默认昵称
    from_name = current_user.email_from_name or get_provider_config(current_user.email_provider)["name"]

    result = email_service.send_email(
        to=request.to,
        subject=request.subject,
        content=request.content,
        provider=current_user.email_provider,
        email_address=current_user.email_address,
        auth_code=current_user.email_auth_code,
        from_name=from_name
    )

    return EmailSendResponse(
        success=result["success"],
        to=result["to"],
        subject=result["subject"],
        sent_at=result["sent_at"]
    )
