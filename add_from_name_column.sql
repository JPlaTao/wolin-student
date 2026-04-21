-- 为 users 表添加发件人昵称字段
ALTER TABLE users ADD COLUMN email_from_name VARCHAR(50) DEFAULT NULL;