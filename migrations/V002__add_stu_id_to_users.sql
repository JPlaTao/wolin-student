-- V002: 为 users 表添加 stu_id 字段，建立用户-学生映射
-- 用于学生自助查成绩功能

ALTER TABLE users ADD COLUMN stu_id INT NULL AFTER is_active;
ALTER TABLE users ADD UNIQUE INDEX uq_users_stu_id (stu_id);
ALTER TABLE users ADD CONSTRAINT fk_users_stu_id FOREIGN KEY (stu_id) REFERENCES stu_basic_info(stu_id);
