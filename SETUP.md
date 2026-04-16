# 沃林学生管理系统 - 项目启动指南

## 📋 前置要求

- Python 3.8 或更高版本
- MySQL 5.7 或更高版本
- pip 包管理器

## 🚀 快速启动

### 1. 克隆项目

```bash
git clone <项目地址>
cd wolin-student
```

### 2. 创建虚拟环境（推荐）

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

在项目根目录创建 `.env` 文件，配置以下内容：

```env
# 数据库配置
SQLALCHEMY_DATABASE_URL=mysql+pymysql://用户名:密码@localhost:3306/数据库名

# JWT 密钥（用于用户认证）
JWT_SECRET_KEY=your-secret-key-change-this-in-production-please

# 阿里云 DashScope API 密钥（用于智能问答）
DASHSCOPE_API_KEY=your-dashscope-api-key-here
```

**获取 DashScope API 密钥：**
1. 访问 https://dashscope.console.aliyun.com/
2. 注册并登录
3. 在 API Key 管理中创建密钥

### 5. 数据库初始化

```bash
# 方式1：使用 SQL 文件（推荐）
mysql -u 用户名 -p 数据库名 < database_init_test.sql

# 方式2：运行 Python 脚本（如果有）
python check_users_table.py
```

### 6. 启动项目

```bash
python main.py
```

服务将在 `http://localhost:8080` 启动

## 🌐 访问地址

- **前端界面：** http://localhost:8080/static/index.html
- **API 文档：** http://localhost:8080/docs
- **ReDoc 文档：** http://localhost:8080/redoc

## 📁 项目结构

```
wolin-student/
├── api/              # API 路由
│   ├── student_api.py
│   ├── class_api.py
│   ├── teacher_api.py
│   ├── exam_api.py
│   ├── employment_api.py
│   ├── statistics_api.py
│   ├── query_agent.py
│   └── auth_api.py
├── core/             # 核心功能
│   ├── database.py    # 数据库连接
│   └── auth.py       # 认证逻辑
├── dao/              # 数据访问层
├── model/            # ORM 模型
├── schemas/          # Pydantic 模型
├── services/         # 业务逻辑
├── middleware/       # 中间件
├── static/           # 前端文件
│   ├── index.html
│   ├── css/
│   └── js/
├── docs/             # 知识库文档
├── logs/             # 日志文件
├── tests/            # 测试文件
├── main.py           # 应用入口
├── requirements.txt   # 依赖列表
└── .env             # 环境变量配置（需自行创建）
```

## 🔑 默认用户

系统启动后需要注册用户，或手动在数据库中插入管理员用户。

**创建管理员用户（通过前端注册）：**
1. 访问 http://localhost:8080/static/index.html
2. 点击"注册"
3. 选择角色为"管理员"
4. 完成注册

## 📝 功能说明

### 数据看板
- 学生总数、班级数量、平均年龄、就业率统计
- 班级男女比例图表
- 各班平均成绩排名
- 薪资前五名

### 智能问答
- 支持自然语言查询学生、班级、教师、成绩、就业数据
- 支持多轮对话记忆
- 基于知识库的智能问答

### 高级统计
- 薪资分布区间分析
- 班级平均就业时长统计
- 每次考试班级平均分排名

### 数据管理
- **学生管理：** 增删改查学生信息
- **班级管理：** 管理班级信息
- **教师管理：** 管理教师信息
- **成绩管理：** 管理考试成绩
- **就业管理：** 管理学生就业信息

### 用户管理（仅管理员）
- 创建/编辑/删除系统用户
- 设置用户角色（管理员/教师/学生/普通用户）
- 启用/禁用用户账户

## 🐛 常见问题

### 1. 数据库连接失败
- 检查 `.env` 文件中的数据库配置是否正确
- 确保 MySQL 服务已启动
- 确保数据库用户有足够的权限

### 2. 知识库构建失败
- 检查 `DASHSCOPE_API_KEY` 是否正确配置
- 确保网络连接正常（需要访问阿里云服务）
- 知识库构建失败不影响其他功能使用

### 3. 智能问答不工作
- 确保已正确配置 `DASHSCOPE_API_KEY`
- 检查 `docs/` 目录下是否有文档文件
- 查看 `logs/` 目录下的日志文件

### 4. PyCharm 显示项目文件为黄色
- 这是 `.gitignore` 配置问题，不影响项目运行
- 可以忽略，或在 PyCharm 设置中调整
- 详见项目 `.gitignore` 文件

## 📞 技术支持

如有问题，请检查 `logs/` 目录下的日志文件，或联系开发团队。

## 📄 许可证

详见 LICENSE 文件
