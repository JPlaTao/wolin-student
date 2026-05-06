# 架构评估 + 学生自助查成绩功能计划

## 一、当前架构评估

### 优点
| 维度 | 评价 |
|------|------|
| **分层架构** | API → Service → DAO → Model，职责清晰 |
| **认证体系** | JWT + `require_role()` 依赖注入，统一且可扩展 |
| **错误处理** | 类型化异常体系 + 全局处理器，标准化 JSON 响应 |
| **前端结构** | 工厂函数模块化，单文件入口编排，无构建依赖 |
| **角色支持** | 代码中已定义 `admin/teacher/student` 三个角色，前端 `hasRole()` 可用 |

### 不足（与本次需求相关的）
| 问题 | 影响 |
|------|------|
| **User 模型缺少 stu_id** | 无法将登录用户映射到学生实体，student 角色无法查询"自己的"成绩 |
| **所有 exam 端点 require_role(["admin","teacher"])** | student 角色 HTTP 403 |
| **management.js 是单体文件 (504 行)** | 改动容易引入回归 |
| **management/ 子模块是死代码** | 重构未完成，子模块未接入 app.js |
| **成绩表无分页** | 数据量大了以后会卡 |

---

## 二、功能可行性

**结论：可以实现，改动量中等（后端 3 个文件 + 迁移，前端 3 个文件）。**

### 核心设计思路

不修改现有 admin/teacher 的流程，在**现有架构上扩展**：

1. User 模型加 `stu_id` 字段 → 建立用户-学生映射
2. 新增 `GET /exam/my-scores` 端点 → 学生专用，只能查自己的成绩
3. 前端数据管理 Tab 对 student 角色开放 → 只显示成绩子 tab，只读模式

---

## 三、详细改动计划

### Step 1: User 模型加 `stu_id`（后端）

**文件**: `model/user.py`

```python
# 新增字段
stu_id = Column(Integer, ForeignKey("stu_basic_info.stu_id"), nullable=True, unique=True)
```

并建立 relationship 到 `StuBasicInfo`。

**迁移**: 在 `model/` 下创建 `alembic` 或手写 SQL 脚本：

```sql
ALTER TABLE users ADD COLUMN stu_id INT NULL;
ALTER TABLE users ADD FOREIGN KEY (stu_id) REFERENCES stu_basic_info(stu_id);
ALTER TABLE users ADD UNIQUE (stu_id);
```

迁移后运行一次即可。

### Step 2: 注册时自行绑定 stu_id

**文件**: `api/auth_api.py`，修改 `UserCreate` schema 增加可选的 `stu_id`：

```python
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"
    stu_id: Optional[int] = None  # 新增
```

在 `register()` 函数中增加验证逻辑：
- 如果提供 `stu_id`，校验其在 `stu_basic_info` 表中存在
- 如果存在，直接绑定到新创建的 User
- 如果不存在，返回验证错误

```python
if user_create.stu_id is not None:
    student = db.query(StuBasicInfo).filter(
        StuBasicInfo.stu_id == user_create.stu_id,
        StuBasicInfo.is_deleted == False
    ).first()
    if not student:
        raise ValidationException(message="学号不存在", ...)
    # 可选：检查该 stu_id 是否已被其他用户绑定
    existing = db.query(User).filter(User.stu_id == user_create.stu_id).first()
    if existing:
        raise ConflictException(message="该学生已被其他账号绑定", ...)
    new_user.stu_id = user_create.stu_id
```

**前端 `auth.js` 修改**: 注册表单增加 `stu_id` 输入框（仅在角色为 student 时显示）。

### Step 3: 后端新增学生查分端点

**文件**: `api/exam_api.py` — 新增一个端点：

```python
@router_exam.get("/my-scores", response_model=response.ListResponse, description="学生查看自己的成绩")
async def exam_get_my_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["student"]))
):
    if current_user.stu_id is None:
        raise BusinessException(message="未绑定学生信息", detail="当前用户未关联学生记录")
    records = exam_dao.exam_get(current_user.stu_id, None, db)
    return response.ListResponse(data=records.get("data", []), total=len(records.get("data", [])))
```

### Step 3: 前端 — 数据管理 Tab 对 student 开放

**文件**: `static/index.html`
- 行 193: `v-if="hasRole('admin', 'teacher')"` → `v-if="hasRole('admin', 'teacher', 'student')"`
- 行 573: 数据管理外层 div 同样改为 `v-if="activeTab === 'management' && hasRole('admin', 'teacher', 'student')"`

### Step 4: 前端 — 条件渲染子 Tab

**文件**: `static/index.html`，在成绩管理 `<el-tab-pane>` 上加以下控制：

让非 admin/teacher 的子 tab 不显示：

```html
<el-tab-pane label="学生管理" name="student" v-if="hasRole('admin', 'teacher')">
<el-tab-pane label="班级管理" name="class" v-if="hasRole('admin', 'teacher')">
<el-tab-pane label="教师管理" name="teacher" v-if="hasRole('admin', 'teacher')">
<el-tab-pane label="成绩管理" name="exam"><!-- 始终显示 --></el-tab-pane>
<el-tab-pane label="就业管理" name="employment" v-if="hasRole('admin', 'teacher')">
```

当 student 登录时，只有 "成绩管理" 会显示。

### Step 5: 前端 — 学生只读成绩视图

**文件**: `static/index.html`，在成绩管理 tab 内，用 `hasRole('student')` 条件渲染不同内容：

```html
<!-- 学生只读视图 -->
<template v-if="hasRole('student')">
  <div class="mb-4">
    <el-button type="default" @click="loadMyExamScores">
      <i class="fas fa-sync-alt"></i> 刷新
    </el-button>
  </div>
  <el-table :data="myExamRecords" stripe v-loading="myExamLoading">
    <el-table-column prop="seq_no" label="考试序号" width="100"></el-table-column>
    <el-table-column prop="grade" label="成绩" width="80"></el-table-column>
    <el-table-column prop="exam_date" label="考试日期" width="120"></el-table-column>
  </el-table>
</template>
<!-- admin/teacher 完整视图（现有代码不变）-->
<template v-else>
  ...现有代码...
</template>
```

**文件**: `static/js/modules/management.js` — 新增学生查分方法：

```javascript
const myExamRecords = ref([]);
const myExamLoading = ref(false);

const loadMyExamScores = async () => {
    myExamLoading.value = true;
    try {
        const res = await axios.get('/exam/my-scores');
        myExamRecords.value = res.data.data || [];
    } catch (err) {
        ElMessage.error('加载成绩失败');
        myExamRecords.value = [];
    } finally {
        myExamLoading.value = false;
    }
};
```

并添加到 return 对象中。

**文件**: `static/js/app.js`，在 `onMounted`、登录后初始化、以及 `watch(activeTab)` 中增加：

```javascript
// 当 student 激活 management tab 时加载其成绩
if (newVal === 'management') {
    if (auth.hasRole('student')) {
        await mgmt.loadMyExamScores();
    } else {
        await mgmt.loadManagementData();
        // ...现有逻辑...
    }
}
```

---

## 四、改动的文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `model/user.py` | 修改 | 新增 `stu_id` 字段 + FK + relationship |
| `model/__init__.py` | 可能修改 | 确保 `StuBasicInfo` 可导入 |
| 迁移 SQL 脚本 | 新增 | `stu_id` 列 + FK + unique |
| `api/exam_api.py` | 修改 | 新增 `GET /exam/my-scores` 端点 |
| `api/auth_api.py` | 修改 | 新增 `PUT /auth/users/{id}/link-student` 端点 |
| `static/index.html` | 修改 | 侧边栏/数据管理 Tab 对 student 开放 + 条件渲染子 Tab + 学生只读表格 |
| `static/js/modules/management.js` | 修改 | 新增 `loadMyExamScores` 方法及相关响应式状态 |
| `static/js/app.js` | 修改 | 添加 student 角色下的数据加载编排 |

---

## 五、不需要改动的部分

- **new API router / prefix** — 复用 `router_exam` 和 ``router``
- **DAO 层** — `exam_dao.exam_get()` 已支持按 `stu_id` 查询
- **Service 层** — 直接调用 DAO 即可（与现有 exam 模式一致）
- **现有 admin/teacher 流程** — 完全不受影响
- **角色系统 / permissions.py** — 现有角色体系完全够用

---

## 六、验证方法

1. **启动服务**: `.venv/Scripts/python main.py`
2. **迁移验证**: 连接 MySQL 确认 `users` 表已有 `stu_id` 列
3. **API 测试**:
   - `POST /auth/login` 以 student 身份登录 → 拿 token
   - `GET /exam/my-scores` 带 student token → 只返回该学生成绩
   - `GET /exam/records` 带 student token → 403
4. **前端验证**:
   - 用 student 账号登录 → 侧边栏出现"数据管理"
   - 点击"数据管理" → 只显示"成绩管理"一个子 Tab
   - 表格中只有自己的成绩，无编辑/删除按钮
   - 用 admin/teacher 账号登录 → 不受影响
5. **管理员绑定验证**: 用 admin 账号通过用户管理界面，将用户关联到学生
