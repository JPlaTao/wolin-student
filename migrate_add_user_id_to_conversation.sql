-- ============================================
-- 数据库迁移脚本：为 conversation_memory 表添加 user_id 字段
-- 目的：实现会话与用户身份的关联，防止会话劫持和隐私泄露
-- 创建时间: 2026-04-17
-- ============================================

USE wolin_test1;

-- 1. 添加 user_id 字段
ALTER TABLE conversation_memory 
ADD COLUMN user_id INT NULL COMMENT '用户ID，关联users表';

-- 2. 添加复合索引（user_id + session_id），提升查询性能
CREATE INDEX idx_user_session ON conversation_memory (user_id, session_id);

-- 3. 为现有数据清空或标记（根据实际情况选择）
-- 选项 A：清空现有数据（推荐，生产环境）
-- TRUNCATE TABLE conversation_memory;

-- 选项 B：标记为无主数据（测试环境，保留数据用于测试）
-- 这里选择清空，因为现有数据没有用户关联，存在安全风险
TRUNCATE TABLE conversation_memory;

-- 4. 修改字段为 NOT NULL（确保后续插入必须有 user_id）
ALTER TABLE conversation_memory 
MODIFY COLUMN user_id INT NOT NULL COMMENT '用户ID，关联users表';

-- ============================================
-- 验证迁移结果
-- ============================================
DESCRIBE conversation_memory;

SELECT COUNT(*) as total_records FROM conversation_memory;

-- ============================================
-- 注意事项：
-- 1. 执行前请备份数据库
-- 2. 执行后需要重启应用以加载新的模型定义
-- 3. API 代码需要同步修改以传入 user_id 参数
-- ============================================
