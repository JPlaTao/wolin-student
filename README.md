

# Wolin Students 教育管理系统

一个基于 FastAPI 和 SQLAlchemy 构建的完整教育管理系统，提供学生、班级、教师、就业信息、考试管理等核心功能的 RESTful API 接口。

## 项目简介

Wolin Students 是一个面向教育机构的信息管理系统，采用前后端分离架构，后端使用 Python FastAPI 框架构建 RESTful API，结合 SQLAlchemy 实现数据库操作。系统支持学生信息管理、班级管理、教师管理、就业跟踪、考试成绩管理以及数据统计分析等功能。

## 技术栈

- **Web 框架**: FastAPI
- **数据库 ORM**: SQLAlchemy
- **数据库**: MySQL
- **数据验证**: Pydantic
- **Python 版本**: 3.x

## 功能模块

### 1. 学生管理 (Student API)
- 获取学生列表（支持按学号、姓名、班级筛选）
- 创建新学生
- 更新学生信息
- 删除学生

### 2. 班级管理 (Class API)
- 获取所有班级
- 获取单个班级信息
- 创建班级
- 更新班级信息
- 删除班级

### 3. 教师管理 (Teacher API)
- 获取教师列表
- 获取教师信息
- 创建教师
- 更新教师信息
- 删除教师
- 查询教师授课班级
- 查询教师担任班主任的班级
- 查询教师负责的就业学生

### 4. 就业管理 (Employment API)
- 查询就业信息（支持多条件筛选）
- 更新就业信息
- 删除就业记录

### 5. 考试管理 (Exam API)
- 提交考试成绩

### 6. 统计分析 (Statistics API)
- 30岁以上学生统计
- 班级男女比例统计
- 班级平均分排名
- 不及格学生名单
- 薪资 TOP5
- 各公司就业人数统计
- 数据总览仪表盘

## 项目结构

```
WolinStudents/
├── api/                    # API 路由层
│   ├── class_api.py       # 班级管理接口
│   ├── employment_api.py  # 就业管理接口
│   ├── exam_api.py        # 考试管理接口
│   ├── statistics_api.py  # 统计分析接口
│   ├── student_api.py     # 学生管理接口
│   └── teacher_api.py     # 教师管理接口
├── dao/                   # 数据访问层
│   ├── class_dao.py
│   ├── employment_dao.py
│   ├── exam_dao.py
│   ├── student_dao.py
│   └── teacher_dao.py
├── model/                 # 数据库模型
│   ├── class_model.py
│   ├── employment.py
│   ├── exam_model.py
│   ├── student.py
│   └── teachers.py
├── schemas/               # Pydantic 数据模型
│   ├── class_schemas.py
│   ├── exam_request.py
│   ├── response.py
│   └── stu_request.py
├── database.py            # 数据库配置
├── main.py                # 应用入口
├── requirements.txt      # 依赖包
└── wolin_test1.sql       # 数据库初始化脚本
```

## 快速开始

### 环境要求

- Python 3.7+
- MySQL 5.7+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置数据库

请根据实际环境修改 `database.py` 中的数据库连接配置。

### 初始化数据库

```bash
mysql -u root -p