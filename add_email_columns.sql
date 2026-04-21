-- 为 users 表添加邮箱绑定字段
-- 执行此 SQL 前请备份数据库

ALTER TABLE users ADD COLUMN email_provider VARCHAR(20) DEFAULT NULL COMMENT '邮箱服务商: qq, 163';
ALTER TABLE users ADD COLUMN email_address VARCHAR(100) DEFAULT NULL COMMENT '用户邮箱地址';
ALTER TABLE users ADD COLUMN email_auth_code VARCHAR(100) DEFAULT NULL COMMENT '邮箱授权码';
