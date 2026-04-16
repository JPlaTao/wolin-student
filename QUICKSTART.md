# 快速开始指南

## 一分钟启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `.env.example` 为 `.env` 并填写配置：
```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
SQLALCHEMY_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/wolin_db
JWT_SECRET_KEY=your-secret-key-change-this
DASHSCOPE_API_KEY=your-dashscope-api-key
```

### 3. 初始化数据库
```bash
mysql -u root -p wolin_db < database_init_test.sql
```

### 4. 启动服务
```bash
python main.py
```

### 5. 访问系统
打开浏览器访问：http://localhost:8080/static/index.html

---

## 详细配置

详见 [SETUP.md](./SETUP.md)
