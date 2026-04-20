import smtplib
s = smtplib.SMTP('smtp.qq.com', 587, timeout=10)
s.starttls()
s.login('jpaltao@qq.com', 'pbydrfozawuueajd')
print("登录成功！")
