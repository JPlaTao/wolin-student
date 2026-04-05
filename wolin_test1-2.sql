-- =============================================
-- 完整重置脚本：清空库 → 重建表 → 插入测试数据
-- 数据库：wolin_test1
-- =============================================

-- 1. 重置数据库（删除并重建，清空所有数据）
DROP DATABASE IF EXISTS wolin_test1;
CREATE DATABASE wolin_test1 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE wolin_test1;

-- 2. 重建所有表（含最新字段）
-- 教师表
CREATE TABLE teacher (
    teacher_id INT AUTO_INCREMENT PRIMARY KEY,
    teacher_name VARCHAR(30) NULL COMMENT '姓名',
    role VARCHAR(20) NULL COMMENT '角色：counselor顾问/headteacher班主任/lecturer讲师',
    is_deleted TINYINT(1) DEFAULT 0 NOT NULL COMMENT '逻辑删除：0-未删除，1-已删除'
) COMMENT='教师信息表';

-- 班级表
CREATE TABLE class (
    class_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '班级编号',
    class_name VARCHAR(50) NOT NULL COMMENT '班级名称',
    start_time DATETIME NOT NULL COMMENT '开课时间',
    head_teacher_id INT NULL COMMENT '班主任ID'
) COMMENT='班级信息表';

-- 班级-教师关联表
CREATE TABLE class_teacher (
    class_id INT NOT NULL COMMENT '班级ID',
    teacher_id INT NOT NULL COMMENT '教师ID',
    PRIMARY KEY (class_id, teacher_id),
    CONSTRAINT fk_ct_class FOREIGN KEY (class_id) REFERENCES class(class_id),
    CONSTRAINT fk_ct_teacher FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id)
) COMMENT='班级教师关联表';

-- 学生基础信息表
CREATE TABLE stu_basic_info (
    stu_id INT AUTO_INCREMENT PRIMARY KEY,
    stu_name VARCHAR(20) NOT NULL,
    class_id INT NOT NULL COMMENT '班级ID（外键）',
    native_place VARCHAR(50) NOT NULL COMMENT '籍贯',
    graduated_school VARCHAR(50) NOT NULL COMMENT '毕业院校',
    major VARCHAR(50) NOT NULL COMMENT '专业',
    admission_date DATETIME NOT NULL COMMENT '入学日期',
    graduation_date DATETIME NOT NULL COMMENT '毕业日期',
    education VARCHAR(20) NOT NULL COMMENT '学历',
    advisor_id INT NULL COMMENT '顾问ID（外键）',
    age INT NOT NULL,
    gender VARCHAR(2) NOT NULL COMMENT '性别：男/女',
    is_deleted TINYINT(1) DEFAULT 0 NULL,
    CONSTRAINT fk_stu_advisor FOREIGN KEY (advisor_id) REFERENCES teacher(teacher_id),
    CONSTRAINT fk_stu_class FOREIGN KEY (class_id) REFERENCES class(class_id)
) COMMENT='学生基础信息表';

-- 就业信息表（含class_id）
CREATE TABLE employment (
    emp_id INT AUTO_INCREMENT PRIMARY KEY,
    stu_id INT NOT NULL COMMENT '学生ID（外键）',
    stu_name VARCHAR(20) NOT NULL,
    open_time DATE NULL COMMENT '就业开放时间',
    offer_time DATE NULL COMMENT 'offer下发时间',
    company VARCHAR(50) NULL COMMENT '就业公司名称',
    salary FLOAT NULL COMMENT '就业薪资',
    is_deleted INT DEFAULT 0 NULL,
    class_id INT NULL COMMENT '班级ID',
    CONSTRAINT fk_emp_stu FOREIGN KEY (stu_id) REFERENCES stu_basic_info(stu_id) ON DELETE CASCADE
) COMMENT='学生就业信息表';

-- 学生考核记录表
CREATE TABLE stu_exam_record (
    record_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID（主键）',
    stu_id INT NOT NULL COMMENT '学生编号',
    seq_no INT NOT NULL COMMENT '考核序次',
    grade INT NULL COMMENT '考核成绩',
    exam_date DATE NULL COMMENT '考核日期',
    is_deleted INT DEFAULT 0 NULL COMMENT '逻辑删除',
    CONSTRAINT fk_exam_stu FOREIGN KEY (stu_id) REFERENCES stu_basic_info(stu_id)
) COMMENT='学生考核记录表';

-- 3. 插入全套测试数据（每张表10条+，关联完整）
-- 插入教师数据
INSERT INTO teacher (teacher_name, role, is_deleted)
VALUES
('张建国', 'headteacher', 0),('李红梅', 'headteacher', 0),('王志强', 'lecturer', 0),
('刘芳', 'lecturer', 0),('陈明', 'counselor', 0),('赵雅', 'counselor', 0),
('周俊杰', 'headteacher', 0),('吴思远', 'lecturer', 0),('郑晓雨', 'counselor', 0),('马丽', 'headteacher', 0);

-- 插入班级数据
INSERT INTO class (class_name, start_time, head_teacher_id)
VALUES
('Java全栈2501期', '2025-01-10 09:00:00', 1),('Python大数据2502期', '2025-02-15 09:30:00', 2),
('前端开发2503期', '2025-03-05 10:00:00', 7),('软件测试2504期', '2025-04-08 14:00:00', 10),
('Java全栈2505期', '2025-05-12 09:00:00', 1),('Python大数据2506期', '2025-06-20 09:30:00', 2),
('前端开发2507期', '2025-07-10 10:00:00', 7),('软件测试2508期', '2025-08-15 14:00:00', 10),
('云计算运维2509期', '2025-09-01 09:00:00', 7),('网络安全2510期', '2025-10-10 14:30:00', 2);

-- 插入班级-教师关联
INSERT INTO class_teacher (class_id, teacher_id)
VALUES (1,1),(1,3),(1,5),(2,2),(2,4),(2,6),(3,7),(3,3),(3,9),(4,10),(4,4),(4,6),
(5,1),(5,8),(5,5),(6,2),(6,3),(6,9),(7,7),(7,4),(7,6),(8,10),(8,8),(8,5),(9,7),(9,3),(9,9),(10,2),(10,4),(10,6);

-- 插入学生基础信息
INSERT INTO stu_basic_info
(stu_name, class_id, native_place, graduated_school, major, admission_date, graduation_date, education, advisor_id, age, gender, is_deleted)
VALUES
('张三', 1, '北京市', '北京理工大学', '计算机科学', '2025-01-10', '2025-07-10', '本科', 5, 22, '男', 0),
('李四', 1, '上海市', '上海大学', '软件工程', '2025-01-10', '2025-07-10', '本科', 5, 23, '男', 0),
('王芳', 2, '广州市', '华南理工', '信息工程', '2025-02-15', '2025-08-15', '专科', 6, 21, '女', 0),
('刘阳', 2, '深圳市', '深圳大学', '电子信息', '2025-02-15', '2025-08-15', '本科', 6, 24, '男', 0),
('陈明', 3, '杭州市', '浙江大学', '人工智能', '2025-03-05', '2025-09-05', '本科', 9, 22, '男', 0),
('赵雪', 3, '南京市', '南京大学', '数据科学', '2025-03-05', '2025-09-05', '专科', 9, 20, '女', 0),
('周浩', 4, '成都市', '四川大学', '软件技术', '2025-04-08', '2025-10-08', '本科', 6, 23, '男', 0),
('吴佳', 4, '重庆市', '重庆大学', '计算机应用', '2025-04-08', '2025-10-08', '专科', 6, 21, '女', 0),
('郑琪', 5, '武汉市', '武汉大学', '网络工程', '2025-05-12', '2025-11-12', '本科', 5, 24, '女', 0),
('马瑞', 5, '西安市', '西安电子', '通信工程', '2025-05-12', '2025-11-12', '本科', 5, 22, '男', 0);

-- 插入就业信息（含class_id）
INSERT INTO employment
(stu_id, stu_name, open_time, offer_time, company, salary, is_deleted, class_id)
VALUES
(1, '张三', '2025-06-01', '2025-06-15', '百度', 12000, 0, 1),
(2, '李四', '2025-06-05', '2025-06-20', '阿里', 13500, 0, 1),
(3, '王芳', '2025-07-10', '2025-07-25', '腾讯', 11000, 0, 2),
(4, '刘阳', '2025-07-15', '2025-08-01', '字节', 14000, 0, 2),
(5, '陈明', '2025-08-01', '2025-08-15', '美团', 12500, 0, 3),
(6, '赵雪', '2025-08-10', '2025-08-28', '滴滴', 10500, 0, 3),
(7, '周浩', '2025-09-05', '2025-09-20', '京东', 13000, 0, 4),
(8, '吴佳', '2025-09-10', '2025-09-30', '网易', 11500, 0, 4),
(9, '郑琪', '2025-10-01', '2025-10-15', '小米', 12800, 0, 5),
(10, '马瑞', '2025-10-08', '2025-10-22', '华为', 15000, 0, 5);

-- 插入考核记录
INSERT INTO stu_exam_record (stu_id, seq_no, grade, exam_date, is_deleted)
VALUES
(1, 1, 85, '2025-03-15', 0),(1, 2, 92, '2025-05-10', 0),(2, 1, 78, '2025-03-15', 0),(2, 2, 88, '2025-05-10', 0),
(3, 1, 90, '2025-04-10', 0),(3, 2, 86, '2025-06-12', 0),(4, 1, 75, '2025-04-10', 0),(4, 2, 82, '2025-06-12', 0),
(5, 1, 95, '2025-05-08', 0),(6, 1, 80, '2025-05-08', 0),(7, 1, 89, '2025-06-05', 0),(8, 1, 79, '2025-06-05', 0),
(9, 1, 91, '2025-07-10', 0),(10, 1, 84, '2025-07-10', 0);

-- =============================================
-- 执行完成！数据库已重置并填充测试数据
-- =============================================