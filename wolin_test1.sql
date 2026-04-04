create database if not exists wolin_test1 collate utf8mb4_0900_ai_ci;

use wolin_test1

create table if not exists class
(
    class_id   int auto_increment comment '班级编号'
        primary key,
    class_name varchar(50) not null comment '班级名称',
    start_time datetime    not null comment '开课时间'
);

create table if not exists teacher
(
    teacher_id   int auto_increment
        primary key,
    teacher_name varchar(30) null comment '姓名',
    role         varchar(20) null comment '角色：counselor顾问/headteacher班主任/lecturer讲师'
);

create table if not exists class_teacher
(
    class_id   int not null comment '班级ID',
    teacher_id int not null comment '教师ID',
    primary key (class_id, teacher_id),
    constraint fk_ct_class
        foreign key (class_id) references class (class_id),
    constraint fk_ct_teacher
        foreign key (teacher_id) references teacher (teacher_id)
);

create table if not exists stu_basic_info
(
    stu_id           int auto_increment
        primary key,
    stu_name         varchar(20)          not null,
    class_id         int                  not null comment '班级ID（外键）',
    native_place     varchar(50)          not null comment '籍贯',
    graduated_school varchar(50)          not null comment '毕业院校',
    major            varchar(50)          not null comment '专业',
    admission_date   datetime             not null comment '入学日期',
    graduation_date  datetime             not null comment '毕业日期',
    education        varchar(20)          not null comment '学历',
    advisor_id       int                  null comment '顾问ID（外键）',
    age              int                  not null,
    gender           varchar(2)           not null comment '性别：男/女 或 M/F',
    is_deleted       tinyint(1) default 0 null,
    constraint fk_stu_advisor
        foreign key (advisor_id) references teacher (teacher_id),
    constraint fk_stu_class
        foreign key (class_id) references class (class_id)
);

create table if not exists employment
(
    emp_id     int auto_increment
        primary key,
    stu_id     int           not null comment '学生ID（外键）',
    stu_name   varchar(20)   not null,
    open_time  date          null comment '就业开放时间',
    offer_time date          null comment 'offer下发时间',
    company    varchar(50)   null comment '就业公司名称',
    salary     float         null comment '就业薪资',
    is_deleted int default 0 null,
    constraint fk_emp_stu
        foreign key (stu_id) references stu_basic_info (stu_id)
            on delete cascade
);

create table if not exists stu_exam_record
(
--     record_id  int auto_increment comment '自增ID（主键）'
--         primary key,
    stu_id     int           comment '学生编号',
    seq_no     int           comment '考核序次',
    grade      int           null comment '考核成绩',
    exam_date  date          null comment '考核日期',
    is_deleted int default 0 null comment '逻辑删除',
    primary key(stu_id,seq_no),
    constraint fk_exam_stu
        foreign key (stu_id) references stu_basic_info (stu_id)
);


use wolin_test1;

-- 先删除旧表（如果已有数据请备份！）
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS employment;
DROP TABLE IF EXISTS stu_exam_record;
DROP TABLE IF EXISTS class_teacher;
DROP TABLE IF EXISTS stu_basic_info;
DROP TABLE IF EXISTS teacher;
DROP TABLE IF EXISTS class;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. 班级表
CREATE TABLE class
(
    class_id   INT AUTO_INCREMENT COMMENT '班级编号' PRIMARY KEY,
    class_name VARCHAR(50) NOT NULL COMMENT '班级名称',
    start_time DATETIME    NOT NULL COMMENT '开课时间'
);

-- 2. 教师表
CREATE TABLE teacher
(
    teacher_id   INT AUTO_INCREMENT PRIMARY KEY,
    teacher_name VARCHAR(30) NULL COMMENT '姓名',
    role         VARCHAR(20) NULL COMMENT '角色：counselor顾问/headteacher班主任/lecturer讲师'
);

-- 3. 学生表（添加外键）
CREATE TABLE stu_basic_info
(
    stu_id           INT AUTO_INCREMENT PRIMARY KEY,
    stu_name         VARCHAR(20) NOT NULL,
    class_id         INT         NOT NULL COMMENT '班级ID（外键）',
    native_place     VARCHAR(50) NOT NULL COMMENT '籍贯',
    graduated_school VARCHAR(50) NOT NULL COMMENT '毕业院校',
    major            VARCHAR(50) NOT NULL COMMENT '专业',
    admission_date   DATETIME    NOT NULL COMMENT '入学日期',
    graduation_date  DATETIME    NOT NULL COMMENT '毕业日期',
    education        VARCHAR(20) NOT NULL COMMENT '学历',
    advisor_id       INT         NULL COMMENT '顾问ID（外键）',
    age              INT         NOT NULL,
    gender           VARCHAR(2)  NOT NULL COMMENT '性别：男/女 或 M/F',
    is_deleted       TINYINT(1)  NULL DEFAULT 0,

    CONSTRAINT fk_stu_class FOREIGN KEY (class_id) REFERENCES class (class_id),
    CONSTRAINT fk_stu_advisor FOREIGN KEY (advisor_id) REFERENCES teacher (teacher_id)
);

-- 4. 班级-教师中间表
CREATE TABLE class_teacher
(
    class_id   INT NOT NULL COMMENT '班级ID',
    teacher_id INT NOT NULL COMMENT '教师ID',
    PRIMARY KEY (class_id, teacher_id),
    CONSTRAINT fk_ct_class FOREIGN KEY (class_id) REFERENCES class (class_id),
    CONSTRAINT fk_ct_teacher FOREIGN KEY (teacher_id) REFERENCES teacher (teacher_id)
);

-- 5. 就业记录表
CREATE TABLE employment
(
    emp_id     INT AUTO_INCREMENT PRIMARY KEY,
    stu_id     INT         NOT NULL COMMENT '学生ID（外键）',
    stu_name   VARCHAR(20) NOT NULL,
    open_time  DATE        NULL COMMENT '就业开放时间',
    offer_time DATE        NULL COMMENT 'offer下发时间',
    company    VARCHAR(50) NULL COMMENT '就业公司名称',
    salary     FLOAT       NULL COMMENT '就业薪资',
    is_deleted INT         NULL DEFAULT 0,
    CONSTRAINT fk_emp_stu FOREIGN KEY (stu_id) REFERENCES stu_basic_info (stu_id) ON DELETE CASCADE
);

-- 6. 考试记录表
CREATE TABLE stu_exam_record
(
--     record_id  INT AUTO_INCREMENT COMMENT '自增ID（主键）' PRIMARY KEY,
    stu_id     INT  COMMENT '学生编号',
    seq_no     INT  COMMENT '考核序次',
    grade      INT  NULL COMMENT '考核成绩',
    exam_date  DATE NULL COMMENT '考核日期',
    is_deleted INT  NULL DEFAULT 0 COMMENT '逻辑删除',
    primary key(stu_id,seq_no),
    CONSTRAINT fk_exam_stu FOREIGN KEY (stu_id) REFERENCES stu_basic_info (stu_id)
);


-- ========== 1. 插入班级 ==========
INSERT INTO class (class_name, start_time)
VALUES ('Python全栈开发1班', '2025-03-01 09:00:00'),
       ('Java后端开发1班', '2025-03-15 09:00:00'),
       ('AI人工智能1班', '2025-04-01 09:00:00'),
       ('前端开发1班', '2025-02-20 09:00:00');

-- ========== 2. 插入教师 ==========
INSERT INTO teacher (teacher_name, role)
VALUES ('张三', 'headteacher'), -- 班主任
       ('李四', 'lecturer'),    -- 讲师
       ('王五', 'counselor'),   -- 顾问
       ('赵六', 'lecturer'),    -- 讲师
       ('孙七', 'counselor');
-- 顾问

-- ========== 3. 插入班级-教师关联 ==========
INSERT INTO class_teacher (class_id, teacher_id)
VALUES (1, 1), -- Python班 - 张三（班主任）
       (1, 2), -- Python班 - 李四（讲师）
       (1, 3), -- Python班 - 王五（顾问）
       (2, 1), -- Java班 - 张三（班主任）
       (2, 4), -- Java班 - 赵六（讲师）
       (3, 5), -- AI班 - 孙七（顾问）
       (4, 2);
-- 前端班 - 李四（讲师）

-- ========== 4. 插入学生 ==========
INSERT INTO stu_basic_info (stu_name, class_id, native_place, graduated_school, major,
                            admission_date, graduation_date, education, advisor_id, age, gender, is_deleted)
VALUES ('小明', 1, '北京', '北京大学', '计算机科学',
        '2025-03-01', '2025-09-01', '本科', 3, 22, '男', 0),
       ('小红', 1, '上海', '复旦大学', '软件工程',
        '2025-03-01', '2025-09-01', '本科', 3, 21, '女', 0),
       ('小刚', 2, '广州', '中山大学', '网络工程',
        '2025-03-15', '2025-09-15', '本科', 5, 23, '男', 0),
       ('小丽', 3, '深圳', '华南理工', '人工智能',
        '2025-04-01', '2025-10-01', '硕士', 5, 24, '女', 0),
       ('小强', 1, '杭州', '浙江大学', '信息安全',
        '2025-03-01', '2025-09-01', '本科', 3, 22, '男', 0),
       ('小美', 4, '成都', '四川大学', '数字媒体',
        '2025-02-20', '2025-08-20', '本科', NULL, 21, '女', 0);

-- ========== 5. 插入考试记录 ==========
INSERT INTO stu_exam_record (stu_id, seq_no, grade, exam_date, is_deleted)
VALUES (1, 1, 85, '2025-04-01', 0),
       (1, 2, 90, '2025-04-15', 0),
       (2, 1, 88, '2025-04-01', 0),
       (3, 1, 75, '2025-04-10', 0),
       (5, 1, 92, '2025-04-01', 0);

-- ========== 6. 插入就业记录 ==========
INSERT INTO employment (stu_id, stu_name, open_time, offer_time, company, salary, is_deleted)
VALUES (1, '小明', '2025-08-01', '2025-08-15', '字节跳动', 15000.00, 0),
       (2, '小红', '2025-08-01', NULL, NULL, NULL, 0),
       (3, '小刚', '2025-09-01', '2025-09-10', '阿里巴巴', 18000.00, 0);

