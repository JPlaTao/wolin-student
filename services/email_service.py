"""
邮件发送服务
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional

from core.email_providers import get_provider_config
from utils.logger import get_logger

logger = get_logger("email_service")


class EmailService:
    """邮件发送服务"""

    def send_email(
        self,
        to: List[str],
        subject: str,
        content: str,
        provider: str,
        email_address: str,
        auth_code: str,
        from_name: str = None
    ) -> dict:
        """
        发送邮件（从用户配置读取邮箱信息）

        Args:
            to: 收件人列表
            subject: 邮件主题
            content: 邮件内容
            provider: 邮箱服务商 (qq, 163)
            email_address: 用户邮箱地址
            auth_code: 授权码
            from_name: 发件人昵称（可选）

        Returns:
            dict: 发送结果
        """
        logger.info(f"[邮件发送] 收件人={to}, 主题={subject}, 服务商={provider}")

        if not to:
            raise ValueError("收件人不能为空")

        # 获取服务商配置
        provider_config = get_provider_config(provider)
        smtp_host = provider_config["smtp_host"]
        smtp_port = provider_config["smtp_port"]
        use_ssl = provider_config["use_ssl"]
        # 如果没有提供昵称，使用服务商的默认昵称
        if not from_name:
            from_name = provider_config["default_from_name"]

        # 验证邮箱域名与服务商匹配
        email_domain = email_address.split('@')[1] if '@' in email_address else ''
        smtp_domain = smtp_host.replace('smtp.', '').replace('smtps.', '')

        if email_domain != smtp_domain:
            raise ValueError(
                f"邮箱域名与服务商不匹配！\n"
                f"邮箱: {email_address}\n"
                f"服务商: {provider_config['name']} ({smtp_host})\n"
                f"请确保使用与服务商匹配的邮箱地址。"
            )

        try:
            # 创建邮件对象
            msg = MIMEMultipart("alternative")
            # 对发件人名称进行 RFC 2047 编码
            encoded_from_name = Header(from_name, 'utf-8').encode()
            msg["From"] = f"{encoded_from_name} <{email_address}>"
            msg["To"] = ", ".join(to)
            msg["Subject"] = Header(subject, "utf-8")

            # 添加纯文本内容
            text_part = MIMEText(content, "plain", "utf-8")
            msg.attach(text_part)

            # 添加HTML内容
            html_part = MIMEText(content, "html", "utf-8")
            msg.attach(html_part)

            # 连接SMTP服务器并发送
            logger.info(f"[邮件发送] 连接 {smtp_host}:{smtp_port} (SSL={use_ssl})")

            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()

            logger.info(f"[邮件发送] 登录邮箱 {email_address}...")
            server.login(email_address, auth_code)
            logger.info("[邮件发送] 发送邮件...")

            server.sendmail(email_address, to, msg.as_string())
            server.quit()

            sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[邮件发送] 成功: {to}, {subject}")

            return {
                "success": True,
                "to": to,
                "subject": subject,
                "sent_at": sent_at
            }

        except smtplib.SMTPAuthenticationError:
            logger.error("[邮件发送] 认证失败")
            raise ValueError("邮箱认证失败，请检查邮箱地址和授权码是否正确")

        except smtplib.SMTPRecipientsRefused:
            logger.error(f"[邮件发送] 收件人被拒绝: {to}")
            raise ValueError(f"收件人邮箱地址无效: {to}")

        except smtplib.SMTPException as e:
            logger.error(f"[邮件发送] SMTP错误: {e}")
            raise ValueError(f"邮件发送失败: {str(e)}")

        except Exception as e:
            logger.error(f"[邮件发送] 失败: {e}")
            raise ValueError(f"邮件发送失败: {str(e)}")


# 单例模式
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
