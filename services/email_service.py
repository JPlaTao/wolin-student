"""
邮件发送服务
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional

from core.settings import get_settings
from utils.logger import get_logger

logger = get_logger("email_service")


class EmailService:
    """邮件发送服务"""

    def __init__(self):
        self.settings = get_settings().email

    def send_email(
        self,
        to: List[str],
        subject: str,
        content: str,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        use_tls: Optional[bool] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> dict:
        """
        发送邮件

        Args:
            to: 收件人列表
            subject: 邮件主题
            content: 邮件内容
            smtp_host: SMTP服务器地址（可选，默认使用配置）
            smtp_port: SMTP端口（可选，默认使用配置）
            use_tls: 是否使用TLS（可选，默认使用配置）
            username: 发件人邮箱（可选，默认使用配置）
            password: 发件人授权码（可选，默认使用配置）
            from_name: 发件人名称（可选，默认使用配置）

        Returns:
            dict: 发送结果
        """
        logger.info(f"[DEBUG] 收到邮件发送请求: to={to}, subject={subject}")
        logger.info(f"[DEBUG] 原始参数: smtp_host={smtp_host}, smtp_port={smtp_port}, use_tls={use_tls}")
        logger.info(f"[DEBUG] 原始参数: username={username}, password={'***' if password else None}, from_name={from_name}")

        if not self.settings.enabled:
            raise ValueError("邮件功能未启用，请检查配置")

        if not to:
            raise ValueError("收件人不能为空")

        # 使用传入值或默认值
        _smtp_host = smtp_host or self.settings.default_smtp_host
        _smtp_port = smtp_port or self.settings.default_smtp_port
        _use_tls = use_tls if use_tls is not None else self.settings.default_use_tls
        _username = (username or self.settings.default_username or "").strip()
        _password = (password or self.settings.default_password or "").strip()
        _from_name = from_name or self.settings.default_from_name or "学生管理系统"

        logger.info(f"[DEBUG] 解析后参数: _smtp_host={_smtp_host}, _smtp_port={_smtp_port}, _use_tls={_use_tls}")
        logger.info(f"[DEBUG] 解析后参数: _username={_username}, _from_name={_from_name}")

        # 验证必填项
        if not _username:
            raise ValueError("发件人邮箱不能为空，请填写发件人邮箱地址")
        if not _password:
            raise ValueError("授权码不能为空，请填写邮箱授权码（非登录密码）")

        # 验证 SMTP 服务器和发件人邮箱域名是否匹配
        # 例如: smtp.163.com 应该配 @163.com 邮箱
        _smtp_domain = _smtp_host.replace('smtp.', '').replace('smtps.', '')
        _email_domain = _username.split('@')[1] if '@' in _username else ''
        
        if _email_domain and _smtp_domain != _email_domain:
            raise ValueError(
                f"SMTP服务器域名与发件人邮箱不匹配！\n"
                f"当前 SMTP 服务器: {_smtp_host}\n"
                f"当前发件人邮箱: {_username}\n"
                f"请确保 SMTP 服务器域名与邮箱域名一致，例如:\n"
                f"  - smtp.163.com → @163.com\n"
                f"  - smtp.qq.com → @qq.com\n"
                f"  - smtp.gmail.com → @gmail.com"
            )

        try:
            # 创建邮件对象
            msg = MIMEMultipart("alternative")
            # 对发件人名称进行 RFC 2047 编码，防止中文名称导致邮件被拒收
            encoded_from_name = str(Header(_from_name, 'utf-8'))
            msg["From"] = f"{encoded_from_name} <{_username}>"
            msg["To"] = ", ".join(to)
            msg["Subject"] = Header(subject, "utf-8")

            # 添加纯文本内容
            text_part = MIMEText(content, "plain", "utf-8")
            msg.attach(text_part)

            # 添加HTML内容（如果需要）
            html_part = MIMEText(content, "html", "utf-8")
            msg.attach(html_part)

            # 连接SMTP服务器并发送
            logger.info(f"[DEBUG] 正在连接到 {_smtp_host}:{_smtp_port} (use_tls={_use_tls})")
            
            # 根据端口决定连接方式
            # 465 通常使用 SSL，587 使用 STARTTLS
            if _smtp_port == 465 or (_smtp_port != 587 and not _use_tls):
                # 尝试 SSL 连接
                logger.info("[DEBUG] 使用 SSL 连接模式 (SMTP_SSL)")
                server = smtplib.SMTP_SSL(_smtp_host, _smtp_port, timeout=30)
            else:
                # 使用 STARTTLS 连接
                logger.info("[DEBUG] 使用 STARTTLS 连接模式")
                server = smtplib.SMTP(_smtp_host, _smtp_port, timeout=30)
                response = server.ehlo()
                logger.info(f"[DEBUG] EHLO 响应: {response}")
                
                if _use_tls:
                    logger.info("[DEBUG] 正在启用 TLS...")
                    server.starttls()
                    # TLS 后需要再次 EHLO
                    response = server.ehlo()
                    logger.info(f"[DEBUG] TLS 后 EHLO 响应: {response}")

            logger.info(f"[DEBUG] 正在登录邮箱 {_username}...")
            server.login(_username, _password)
            logger.info("[DEBUG] 登录成功，正在发送邮件...")
            
            server.sendmail(_username, to, msg.as_string())
            server.quit()

            sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            logger.info(f"邮件发送成功: 收件人={to}, 主题={subject}")

            return {
                "success": True,
                "to": to,
                "subject": subject,
                "sent_at": sent_at
            }

        except smtplib.SMTPAuthenticationError:
            logger.error(f"邮件发送失败: 认证错误，请检查邮箱和授权码")
            raise ValueError("邮箱认证失败，请检查邮箱地址和授权码是否正确")

        except smtplib.SMTPRecipientsRefused:
            logger.error(f"邮件发送失败: 收件人被拒绝 {to}")
            raise ValueError(f"收件人邮箱地址无效: {to}")

        except smtplib.SMTPException as e:
            logger.error(f"邮件发送失败: SMTP错误 {str(e)}")
            raise ValueError(f"邮件发送失败: {str(e)}")

        except Exception as e:
            logger.error(f"邮件发送失败: {str(e)}")
            raise ValueError(f"邮件发送失败: {str(e)}")


# 单例模式
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
