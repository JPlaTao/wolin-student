# 用户权限系统 — 设计方案

## 问题分析

当前认证体系只有两个层级：`已登录` / `管理员`。所有业务 API 仅靠 `get_current_user` 保护，意味着任何登录用户（包括学生角色）都可以执行增删改查所有操作。注册入口也允许任意指定角色，包括 `admin`。

### 当前问题清单

1. 注册允许任意指定角色（含 admin）
2. 业务 API 无角色校验，任何登录用户可做任何 CRUD
3. JWT token 不含 role，每次请求需查库
4. 无数据隔离（教师看不到"自己的学生"的概念）
5. 前端无角色相关 UI 控制（仅隐藏了用户管理 Tab）
6. `GET /auth/users` 无 admin 检查，存在用户枚举漏洞
7. User 表和 Teacher 表无关联
8. 无集中式 auth middleware

## 目标

1. **权限分级** — 定义清晰的用户角色体系
2. **接口防护** — 业务 API 加角色校验
3. **注册管控** — 禁止普通注册时选 admin
4. **前端配套** — 按角色控制 Tab 和操作按钮
5. **数据隔离** — 教师只看本班数据，学生只看自己数据

## 角色模型

| 角色 | 标识 | 说明 |
|------|------|------|
| 管理员 | `admin` | 全部权限，含用户管理 |
| 教师 | `teacher` | 学生/班级/成绩/就业的 CRUD + AI 工具 |
| 学生 | `student` | 仅查看自身数据 + AI 工具 |

## 权限矩阵

```
操作 \ 角色            admin   teacher   student
──────────────────────────────────────────────────
学生管理 (CRUD)         ✅     ✅(本班)    ❌
班级管理 (CRUD)         ✅     ✅(查看)    ❌
教师管理 (CRUD)         ✅     ✅(查看)    ❌
成绩管理 (CRUD)         ✅     ✅(本班)    ✅(仅自己)
就业管理 (CRUD)         ✅     ✅(本班)    ✅(仅自己)
统计图表                ✅     ✅        待定
智能问答/黛玉/文生图    ✅     ✅         ✅
邮件发送                ✅     ✅         ❌
用户管理                ✅     ❌         ❌
```

## 实现步骤

### Step 1: 权限核心
- JWT payload 加入 `role` 字段
- 新增 `require_role()` 依赖注入工厂函数
- 新增 `core/permissions.py` 定义角色常量

### Step 2: 注册管控 + 用户 API 安全
- 注册时仅允许 `student` / `teacher` 角色
- `GET /auth/users` 改为仅 admin 可访问

### Step 3: 业务 API 逐个加固
- 7 个 API 文件的路由从 `get_current_user` 升级为 `require_role`

### Step 4: 数据隔离 — DAO 层改造
- DAO 查询方法增加 teacher_id / stu_id 过滤参数

### Step 5: 前端权限适配
- auth.js 增加角色状态；index.html 按角色控制 Tab 和按钮

### Step 6: 用户-教师关联（可选）
- User 模型增加 teacher_id 外键

## 涉及文件

| 文件 | 改动类型 |
|------|----------|
| `core/permissions.py` | **新增** |
| `core/auth.py` | 修改 |
| `api/auth_api.py` | 修改 |
| `api/student_api.py` | 修改 |
| `api/class_api.py` | 修改 |
| `api/teacher_api.py` | 修改 |
| `api/exam_api.py` | 修改 |
| `api/employment_api.py` | 修改 |
| `api/email_api.py` | 修改 |
| `dao/student_dao.py` | 修改 |
| `dao/exam_dao.py` | 修改 |
| `dao/employment_dao.py` | 修改 |
| `model/user.py` | 修改（可选） |
| `static/js/modules/auth.js` | 修改 |
| `static/js/app.js` | 修改 |
| `static/index.html` | 修改 |
