"""
邮件发送诊断脚本 - 163 邮箱 SSL 方式
"""
import smtplib

def test_email_connection():
    smtp_host = 'smtp.163.com'
    smtp_port = 465  # 163 用 SSL 端口 465，不是 587！
    username = 'reefield@163.com'
    password = 'YCiqaC2p6EscVmiV'

    try:
        print(f"1. 连接到 {smtp_host}:{smtp_port} (SSL模式)...")
        s = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)  # 关键：SMTP_SSL
        print("   ✓ 连接成功")

        print("2. 尝试登录...")
        s.login(username, password)
        print("   ✓ 登录成功！")

        print("\n✅ 全部测试通过！")
        s.quit()
        return True

    except Exception as e:
        print(f"   ✗ 失败: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    test_email_connection()
