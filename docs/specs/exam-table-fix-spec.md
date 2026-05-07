# P0 — 成绩表加班级/学号列 + 分页

> 状态: 已完成 (2026-05-07) | 优先级: P0 | 预估工时: ~30 min

---

## 一、目标

让成绩管理页面的表格显示**班级名称**和**学号**两列，并对列表加**前端分页**，使管理功能基本可用。

## 二、范围

### 2.1 成绩表格加列

后端 `exam_dao.exam_get_all()` 已用原生 SQL 三表 LEFT JOIN，返回 `stu_name` 和 `class_name`。但前端表格列定义中缺少这两列。

- 前端成绩表格（`management.js` 成绩管理区域）增加 `class_name`、`stu_name` 两列

### 2.2 成绩表分页

当前 `/exam/records` 一次返回全部数据，无分页参数。

- **方案**：前端分页（数据量可控，无需改后端）。用 Element Plus 的 `el-pagination` 组件包裹成绩表格。
- 后端不动 — `GET /exam/records` 直接返全量，前端用 `Array.slice()` 分页切片。

### 2.3 动文件清单

| 文件 | 改动 |
|------|------|
| `static/index.html` | 成绩管理区域加 `class_name`、`stu_name` 列 + `el-pagination` |
| `static/js/modules/management.js` | 加分页相关响应式状态 (`currentPage`, `pageSize`) + `pagedExamRecords` computed |
| `dao/exam_dao.py` | 不动 |
| `api/exam_api.py` | 不动 |

## 三、约束

1. **不改后端** — API 响应格式不变
2. **不改 DAO** — `exam_get_all()` 不变
3. **数据源不变** — `/exam/records` 端点保持不变
4. **分页默认值** — 每页 15 条

## 四、暂不处理

- 后端分页（数据量变大后再改）
- 搜索/筛选功能
- 成绩表排序

## 五、验证方法

1. 启动服务，admin 账号登录
2. 数据管理 → 成绩管理 Tab
3. 确认表格出现"班级"和"姓名"列
4. 确认分页按钮可正常翻页
5. 确认每页 15 条，总数显示正确
