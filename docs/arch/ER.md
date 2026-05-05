```mermaid
erDiagram
    teacher ||--o{ class : "担任班主任"
    teacher ||--o{ class_teacher : "授课"
    teacher ||--o{ stu_basic_info : "担任顾问"
    class ||--o{ class_teacher : "包含教师"
    class ||--o{ stu_basic_info : "包含学生"
    class ||--o{ employment : "学生就业"
    stu_basic_info ||--o{ employment : "就业记录"
    stu_basic_info ||--o{ stu_exam_record : "考试记录"
    users ||--|| users : "系统用户"

    teacher {
        int teacher_id PK "教师ID"
        varchar teacher_name "姓名"
        varchar gender "男/女"
        varchar phone "电话号码"
        varchar role "角色"
        tinyint is_deleted "逻辑删除"
    }

    class {
        int class_id PK "班级编号"
        varchar class_name "班级名称"
        datetime start_time "开课时间"
        tinyint is_deleted "是否删除"
        int head_teacher_id FK "班主任ID"
    }

    class_teacher {
        int class_id PK,FK "班级ID"
        int teacher_id PK,FK "教师ID"
    }

    stu_basic_info {
        int stu_id PK "学生ID"
        varchar stu_name "姓名"
        varchar native_place "籍贯"
        varchar graduated_school "毕业院校"
        varchar major "专业"
        datetime admission_date "入学日期"
        datetime graduation_date "毕业日期"
        varchar education "学历"
        int age "年龄"
        varchar gender "性别"
        int is_deleted "逻辑删除"
        int advisor_id FK "顾问ID"
        int class_id FK "班级ID"
    }

    stu_exam_record {
        int stu_id PK,FK "学生编号"
        int seq_no PK "考核序次"
        int grade "成绩"
        date exam_date "考试日期"
        int is_deleted "逻辑删除"
    }

    employment {
        int emp_id PK "就业ID"
        int stu_id FK "学生ID"
        varchar stu_name "学生姓名"
        int class_id "班级ID"
        date open_time "开放时间"
        date offer_time "offer时间"
        varchar company "公司"
        float salary "薪资"
        tinyint is_deleted "逻辑删除"
    }

    users {
        int id PK "用户ID"
        varchar username UK "用户名"
        varchar hashed_password "密码"
        tinyint is_active "是否激活"
    }
```
