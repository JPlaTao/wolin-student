# Wolin Students 教育管理系统

一个基于 FastAPI 和 SQLAlchemy 构建的完整教育管理系统，提供学生、班级、教师、就业信息、考试管理等核心功能的 RESTful API 接口。

## 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [功能模块](#功能模块)
- [数据库设计](#数据库设计)
- [API 接口文档](#api-接口文档)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [开发规范](#开发规范)
- [测试说明](#测试说明)
- [部署说明](#部署说明)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 项目简介

Wolin Students 是一个面向教育机构的信息管理系统，采用前后端分离架构，后端使用 Python FastAPI 框架构建 RESTful API，结合 SQLAlchemy 实现数据库操作。系统支持学生信息管理、班级管理、教师管理、就业跟踪、考试成绩管理以及数据统计分析等功能。

### 项目背景

本项目旨在为教育培训机构提供一个完整的学生管理系统，帮助机构高效管理学生信息、班级信息、教师信息、就业信息和考试成绩等数据，并提供丰富的统计分析功能，为管理决策提供数据支持。

### 核心特性

- **RESTful API 设计**：遵循 RESTful 设计原则，提供清晰、规范的 API 接口
- **分层架构**：采用 API 层、DAO 层、Model 层的三层架构，代码结构清晰
- **数据验证**：使用 Pydantic 进行请求数据验证，确保数据安全
- **逻辑删除**：支持逻辑删除，保留历史数据
- **统计分析**：提供丰富的统计分析功能，支持数据可视化
- **自动文档**：FastAPI 自动生成 Swagger 文档，方便接口测试和调试

## 技术栈

| 技术 | 版本 | 说明 |
|------|------|------|
| **Python** | 3.10+ | 编程语言 |
| **FastAPI** | 0.135.3 | 现代、快速的 Web 框架 |
| **SQLAlchemy** | 2.0.49 | Python SQL 工具包和 ORM |
| **Pydantic** | 2.12.5 | 数据验证和设置管理 |
| **MySQL** | 5.7+ | 关系型数据库 |
| **Uvicorn** | 0.43.0 | ASGI 服务器 |

### 为什么选择这些技术？

- **FastAPI**：高性能、易学易用、自动生成文档、类型提示支持
- **SQLAlchemy**：功能强大的 ORM，支持多种数据库，灵活的查询 API
- **Pydantic**：运行时数据验证，与 FastAPI 完美集成
- **MySQL**：成熟稳定的关系型数据库，适合教育管理系统的数据存储需求

## 功能模块

### 1. 学生管理 (Student API)
**负责人**: 胡雪松

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 获取学生列表 | GET | `/students/` | 支持按学号、姓名、班级筛选 |
| 创建学生 | POST | `/students/` | 创建新学生，自动创建就业记录 |
| 更新学生信息 | PUT | `/students/{stu_id}` | 更新指定学生的信息 |
| 删除学生 | DELETE | `/students/{stu_id}` | 逻辑删除学生 |

**学生信息字段**：
- 基本信息：学号、姓名、性别、年龄
- 学历信息：籍贯、毕业院校、专业、学历
- 时间信息：入学日期、毕业日期
- 关联信息：班级 ID、顾问 ID

### 2. 班级管理 (Class API)
**负责人**: 杨通辉

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 获取所有班级 | GET | `/class/` | 支持是否包含已删除班级 |
| 获取单个班级 | GET | `/class/{class_id}` | 获取指定班级信息 |
| 创建班级 | POST | `/class/` | 创建新班级 |
| 更新班级 | PUT | `/class/{class_id}` | 更新班级信息 |
| 删除班级 | DELETE | `/class/{class_id}` | 支持逻辑删除和硬删除 |
| 恢复班级 | POST | `/class/{class_id}/restore` | 恢复已删除的班级 |

**班级信息字段**：
- 基本信息：班级编号、班级名称
- 时间信息：开课时间
- 关联信息：班主任 ID

### 3. 教师管理 (Teacher API)
**负责人**: 王雄

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 获取所有教师 | GET | `/teacher/` | 获取教师列表 |
| 获取单个教师 | GET | `/teacher/{teacher_id}` | 获取指定教师信息 |
| 创建教师 | POST | `/teacher/` | 创建新教师 |
| 更新教师 | PUT | `/teacher/{teacher_id}` | 更新教师信息 |
| 删除教师 | DELETE | `/teacher/{teacher_id}` | 删除教师 |
| 获取管理的班级 | GET | `/teacher/{teacher_id}/head_classes` | 获取班主任管理的班级 |
| 获取教授的班级 | GET | `/teacher/{teacher_id}/teach_classes` | 获取教师教授的班级 |
| 获取负责的学生 | GET | `/teacher/{teacher_id}/my_students` | 获取顾问负责的学生 |

**教师角色类型**：
- `counselor`：顾问
- `headteacher`：班主任
- `lecturer`：讲师

### 4. 考试管理 (Exam API)
**负责人**: 赵育聪

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 提交成绩 | POST | `/exam/` | 提交学生考试成绩 |
| 修改成绩 | PUT | `/exam/` | 修改学生考试成绩 |
| 删除成绩 | DELETE | `/exam/{stu_id}` | 删除学生成绩记录 |

**考试成绩字段**：
- 学生 ID
- 考核序次（seq_no）
- 成绩（grade）
- 考核日期（exam_date）

### 5. 就业管理 (Employment API)
**负责人**: 田聪

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 获取学生就业信息 | GET | `/employment/students/{stu_id}` | 获取指定学生的就业信息 |
| 获取班级就业信息 | GET | `/employment/class/{class_id}` | 获取班级所有学生的就业信息 |
| 更新就业信息 | POST | `/employment/students/{stu_id}` | 更新学生就业信息 |
| 删除就业信息 | DELETE | `/employment/delete/{emp_id}` | 逻辑删除就业记录 |
| 恢复就业信息 | PUT | `/employment/restore/{emp_id}` | 恢复已删除的就业记录 |

**就业信息字段**：
- 学生 ID、学生姓名、班级 ID
- 就业开放时间（open_time）
- Offer 下发时间（offer_time）
- 就业公司（company）
- 薪资（salary）

### 6. 统计分析 (Statistics API)
**负责人**: 吕伟建

| 功能 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 测试连通性 | GET | `/statistics/test` | 测试统计接口是否正常 |
| 30岁以上学生统计 | GET | `/statistics/student/age-stat` | 统计30岁以上的学生 |
| 班级男女比例 | GET | `/statistics/student/class-gender` | 各班级男女比例统计 |
| 班级平均分排名 | GET | `/statistics/score/class-average` | 各班级平均分排名 |
| 不及格学生名单 | GET | `/statistics/score/fail-list` | 成绩不及格的学生名单 |
| 薪资 TOP5 | GET | `/statistics/job/top-salary` | 薪资最高的5名学生 |
| 公司就业统计 | GET | `/statistics/job/company-stat` | 各公司就业人数统计 |
| 数据总览 | GET | `/statistics/dashboard/all` | 系统数据总览仪表盘 |

## 数据库设计

### 数据库表结构

#### 1. 教师表 (teacher)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| teacher_id | INT | 主键，自增 |
| teacher_name | VARCHAR(30) | 教师姓名 |
| gender | VARCHAR(10) | 性别 |
| phone | VARCHAR(20) | 电话号码 |
| role | VARCHAR(20) | 角色：counselor/headteacher/lecturer |
| is_deleted | TINYINT(1) | 逻辑删除标志 |

#### 2. 班级表 (class)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| class_id | INT | 主键，自增 |
| class_name | VARCHAR(50) | 班级名称 |
| start_time | DATETIME | 开课时间 |
| is_deleted | TINYINT(1) | 逻辑删除标志 |
| head_teacher_id | INT | 班主任 ID（外键） |

#### 3. 学生表 (stu_basic_info)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| stu_id | INT | 主键，自增 |
| stu_name | VARCHAR(20) | 学生姓名 |
| native_place | VARCHAR(50) | 籍贯 |
| graduated_school | VARCHAR(50) | 毕业院校 |
| major | VARCHAR(50) | 专业 |
| admission_date | DATETIME | 入学日期 |
| graduation_date | DATETIME | 毕业日期 |
| education | VARCHAR(20) | 学历 |
| age | INT | 年龄 |
| gender | VARCHAR(2) | 性别 |
| is_deleted | INT | 逻辑删除标志 |
| advisor_id | INT | 顾问 ID（外键） |
| class_id | INT | 班级 ID（外键） |

#### 4. 考试成绩表 (stu_exam_record)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| stu_id | INT | 学生 ID（主键） |
| seq_no | INT | 考核序次（主键） |
| grade | INT | 成绩 |
| exam_date | DATE | 考核日期 |
| is_deleted | INT | 逻辑删除标志 |

#### 5. 就业信息表 (employment)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| emp_id | INT | 主键，自增 |
| stu_id | INT | 学生 ID（外键） |
| stu_name | VARCHAR(20) | 学生姓名 |
| class_id | INT | 班级 ID |
| open_time | DATE | 就业开放时间 |
| offer_time | DATE | Offer 下发时间 |
| company | VARCHAR(50) | 就业公司 |
| salary | FLOAT | 薪资 |
| is_deleted | BOOLEAN | 逻辑删除标志 |

#### 6. 班级教师关联表 (class_teacher)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| class_id | INT | 班级 ID（主键） |
| teacher_id | INT | 教师 ID（主键） |

### 实体关系图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Teacher   │       │    Class    │       │   Student   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ teacher_id  │◄──────│head_teacher │       │   stu_id    │
│ name        │       │  class_id   │◄──────│  class_id   │
│ role        │       │ class_name  │       │  stu_name   │
└─────────────┘       └─────────────┘       │ advisor_id  │◄──┐
      │                     │               └─────────────┘   │
      │                     │                     ▲           │
      │                     │                     │           │
      └─────────────────────┴─────────────────────┘           │
              (多对多关系：class_teacher)                       │
                                                              │
┌─────────────┐       ┌─────────────┐       ┌─────────────┐   │
│    Exam     │       │ Employment  │       │   Teacher   │───┘
├─────────────┤       ├─────────────┤       └─────────────┘
│   stu_id    │       │   emp_id    │
│   seq_no    │       │   stu_id    │
│   grade     │       │   company   │
└─────────────┘       │   salary    │
                      └─────────────┘
```

## API 接口文档

### 通用响应格式

所有 API 返回统一的 JSON 结构：

```json
{
    "code": 200,
    "message": "success",
    "data": {}
}
```

### 列表响应格式

查询列表时，返回包含列表和总数的响应：

```json
{
    "code": 200,
    "message": "success",
    "data": [...],
    "total": 100
}
```

### 错误响应

错误时使用 HTTP 状态码表示错误类型：

| HTTP 状态码 | 说明 |
|------------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 数据验证失败 |
| 500 | 服务器内部错误 |

### API 文档访问

启动服务后，访问以下地址查看完整的 API 文档：

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 5.7+
- pip（Python 包管理器）

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/your-username/wolin-students.git
cd wolin-students
```

2. **创建虚拟环境**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置数据库**

创建 MySQL 数据库：

```sql
CREATE DATABASE wolin_test1 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

修改 `database.py` 中的数据库连接配置：

```python
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://用户名:密码@localhost/数据库名"
```

5. **初始化数据库**

```bash
mysql -u root -p wolin_test1 < database_init_test.sql
```

6. **启动服务**

```bash
# 方式一：直接运行
python main.py

# 方式二：使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

7. **访问 API 文档**

打开浏览器访问 http://localhost:8080/docs 查看 Swagger UI 文档。

## 项目结构

```
WolinStudents/
├── api/                        # API 路由层
│   ├── __init__.py
│   ├── class_api.py           # 班级管理接口
│   ├── employment_api.py      # 就业管理接口
│   ├── exam_api.py            # 考试管理接口
│   ├── statistics_api.py      # 统计分析接口
│   ├── student_api.py         # 学生管理接口
│   └── teacher_api.py         # 教师管理接口
├── dao/                        # 数据访问层
│   ├── __init__.py
│   ├── class_dao.py           # 班级数据访问
│   ├── employment_dao.py      # 就业数据访问
│   ├── exam_dao.py            # 考试数据访问
│   ├── student_dao.py         # 学生数据访问
│   └── teacher_dao.py         # 教师数据访问
├── model/                      # 数据库模型层
│   ├── __init__.py
│   ├── class_model.py         # 班级模型
│   ├── employment.py          # 就业模型
│   ├── exam_model.py          # 考试模型
│   ├── student.py             # 学生模型
│   └── teachers.py            # 教师模型
├── schemas/                    # Pydantic 数据模型
│   ├── __init__.py
│   ├── class_schemas.py       # 班级数据模型
│   ├── emp_schemas.py         # 就业数据模型
│   ├── exam_request.py        # 考试请求模型
│   ├── response.py            # 响应模型
│   ├── student.py             # 学生数据模型
│   └── teacher.py             # 教师数据模型
├── docs/                       # 项目文档
│   ├── API响应到前端的规定.md
│   ├── FastAPI项目需求.pdf
│   ├── 项目需求.md
│   └── 需求分析.txt
├── database.py                 # 数据库配置
├── main.py                     # 应用入口
├── requirements.txt            # 依赖包列表
├── database_init_test.sql      # 数据库初始化脚本
├── test_api.py                 # 基础测试脚本
├── test_enterprise_api.py      # 企业级测试脚本
├── test_report.json            # 测试报告
├── README.md                   # 项目说明文档
├── README.en.md                # 英文说明文档
└── LICENSE                     # 许可证文件
```

### 架构说明

项目采用三层架构设计：

1. **API 层**：处理 HTTP 请求和响应，进行参数验证
2. **DAO 层**：封装数据库操作，提供数据访问接口
3. **Model 层**：定义数据库表结构和实体关系

## 开发规范

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | 小写下划线 | `student_api.py` |
| 类名 | 大驼峰 | `StuBasicInfo` |
| 函数名 | 小写下划线 | `get_students` |
| 变量名 | 小写下划线 | `student_list` |
| 常量名 | 大写下划线 | `DATABASE_URL` |

### API 命名规范

- API 文件：`xxx_api.py`
- DAO 文件：`xxx_dao.py`
- Model 文件：`xxx.py` 或 `xxx_model.py`
- Schema 文件：`xxx.py` 或 `xxx_schemas.py`

### 响应规范

所有 API 返回统一的响应格式，详见 [API 响应规范](docs/API响应到前端的规定.md)。

### 代码风格

- 使用 4 个空格缩进
- 每行代码不超过 120 个字符
- 函数和类添加文档字符串
- 使用类型提示

## 测试说明

### 测试脚本

项目提供两个测试脚本：

1. **test_api.py**：基础测试脚本，覆盖所有 API 端点
2. **test_enterprise_api.py**：企业级测试脚本，包含详细测试报告

### 运行测试

```bash
# 运行基础测试
pytest test_api.py -v

# 运行企业级测试
pytest test_enterprise_api.py -v

# 生成测试覆盖率报告
pytest --cov=. test_api.py
```

### 测试报告

企业级测试脚本会生成 JSON 格式的测试报告（`test_report.json`），包含：

- 测试开始和结束时间
- 总测试数、通过数、失败数
- 测试通过率
- 每个测试用例的详细结果

## 部署说明

### 开发环境

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### 生产环境

使用 Gunicorn + Uvicorn 部署：

```bash
pip install gunicorn

gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

### Docker 部署

创建 `Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

构建并运行：

```bash
docker build -t wolin-students .
docker run -d -p 8080:8080 wolin-students
```

## 常见问题

### 1. 数据库连接失败

**问题**：启动时报错 `Can't connect to MySQL server`

**解决方案**：
- 检查 MySQL 服务是否启动
- 检查 `database.py` 中的数据库连接配置是否正确
- 确保数据库用户有足够的权限

### 2. 模块导入错误

**问题**：启动时报错 `ModuleNotFoundError: No module named 'xxx'`

**解决方案**：
- 确保已激活虚拟环境
- 运行 `pip install -r requirements.txt` 安装所有依赖

### 3. 端口被占用

**问题**：启动时报错 `Address already in use`

**解决方案**：
- 修改 `main.py` 中的端口号
- 或使用 `--port` 参数指定其他端口

### 4. 数据验证失败

**问题**：API 请求返回 422 错误

**解决方案**：
- 检查请求参数是否符合 Schema 定义
- 查看 Swagger 文档中的请求示例

## 贡献指南

我们欢迎所有形式的贡献，包括但不限于：

- 提交 Bug 报告
- 提出新功能建议
- 提交代码改进
- 完善文档

### 提交代码

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### 代码审查

所有提交的代码都需要经过代码审查，请确保：

- 代码风格符合项目规范
- 添加了必要的测试
- 更新了相关文档

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue：[GitHub Issues](https://github.com/your-username/wolin-students/issues)
- 邮件：your-email@example.com

---

**感谢您使用 Wolin Students 教育管理系统！**
