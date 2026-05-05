# 项目 API 响应规范

## 一、泛型是什么（新手版）

### 一句话解释
泛型 = **"类型的占位符"**，让你写一次模板，就能套用到多种具体类型上。

### 生活中的类比

想象你要寄快递：
- **没有泛型**：箱子贴标签写"里面可能是任何东西" → 快递员不知道咋处理
- **有泛型**：箱子贴标签写"里面是手机"或"里面是衣服" → 快递员一眼知道咋处理

代码里就是：
```python
# 没有泛型：data 可能是任何东西，IDE 不知道里面有什么
class Response:
    data: Any  # 可能是字典、列表、字符串...谁都不知道

# 有泛型：data 类型明确写清楚，IDE 自动提示
class Response[Student]:     # data 必须是 Student 类型
class Response[List[Student]]:  # data 必须是 Student 列表
class Response[str]:        # data 必须是字符串

```
### 代码对比

| 场景 | 没有泛型（旧） | 有泛型（新） |
|------|-------------|------------|
| 创建学生 | `data: Any` 可能是任何东西 | `data: Student` 明确是学生对象 |
| 查询列表 | `data: Any` 可能是任何东西 | `data: StudentList` 明确是列表包装 |
| 写代码时 | IDE 不提示，容易写错字段 | IDE 自动提示 `stu_name` 等字段 |
| 运行时 | 错了才发现 | 启动时就检查类型 |

### 本项目怎么用

```python
# 1. 定义响应结构（带占位符 T）
class Response[T](BaseModel):
    code: int
    message: str
    data: T  # T 就是占位符，用时再填

# 2. 使用时指定 T 是什么
Response[Student]           # data 必须是 Student
Response[StudentList]       # data 必须是 StudentList  
Response[str]             # data 必须是字符串
Response[dict]            # data 必须是字典
```

---

## 二、响应规则总览

所有 API 返回统一的 JSON 结构：

```json
{
    "code": 200,           // 业务状态码（成功时 200/201）
    "message": "success",  // 提示信息
    "data": {}             // 具体数据（类型由泛型指定）
}
```

### 三条铁律
 
| 规则 | 说明 | 错误示例 |
|------|------|---------|
| **1. 顶层固定三字段** | 必须是 `code` + `message` + `data`，不能多不能少 | 直接返回 `{"stu_id": 1}` ❌ |
| **2. data 类型要明确** | 用泛型 `Response[Student]` 指定，不能用 `Any` | `data: Any` ❌ |
| **3. 失败用真实 HTTP 码** | 404 就用 HTTP 404，不要 HTTP 200 + code 404 | `HTTP 200 + {"code": 404}` ❌ |

---

## 三、具体场景示例

### 场景 1：创建学生（返回单个对象）

```python
# API 定义
@router.post("/", response_model=Response[Student])
def create_student(...):
    new_student = dao.create(...)  # 获取 ORM 对象
    return Response[Student](
        code=201,
        message="创建成功",
        data=Student.model_validate(new_student)  # ORM → Pydantic
    )
```

响应：
```json
HTTP 201 Created
{
    "code": 201,
    "message": "创建成功",
    "data": {
        "stu_id": 8,
        "stu_name": "张三",
        "class_id": 2,
        "native_place": "河南",
        "graduated_school": "河南大学",
        "major": "计算机",
        "admission_date": "2025-03-01T00:00:00",
        "graduation_date": "2025-09-01T00:00:00",
        "education": "本科",
        "advisor_id": 3,
        "age": 22,
        "gender": "男",
        "is_deleted": false
    }
}
```

---

### 场景 2：查询列表（返回列表+总数）

```python
# 先定义列表包装类
class StudentList(BaseModel):
    list: List[Student]
    total: int

# API 定义
@router.get("/", response_model=Response[StudentList])
def get_students(...):
    students = dao.get_list(...)  # 获取 ORM 列表
    return Response[StudentList](
        code=200,
        message="查询成功",
        data=StudentList(
            list=[Student.model_validate(s) for s in students],  # 逐个转换
            total=len(students)
        )
    )
```

响应：
```json
HTTP 200 OK
{
    "code": 200,
    "message": "查询成功",
    "data": {
        "list": [
            {"stu_id": 1, "stu_name": "小明", ...},
            {"stu_id": 2, "stu_name": "小红", ...}
        ],
        "total": 2
    }
}
```

---

### 场景 3：操作成功但无数据（如删除）

```python
@router.delete("/{stu_id}", response_model=Response[Student])
def delete_student(stu_id: int, ...):
    deleted = dao.delete(stu_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="学生不存在")  # 真实 HTTP 404
    
    return Response[Student](
        code=200,
        message="删除成功",
        data=Student.model_validate(deleted)  # 返回被删的学生信息
    )
```

成功响应：
```json
HTTP 200 OK
{
    "code": 200,
    "message": "删除成功",
    "data": {
        "stu_id": 1,
        "stu_name": "小明",
        ...
        "is_deleted": true
    }
}
```

失败响应（HTTPException 自动处理）：
```json
HTTP 404 Not Found
{
    "detail": "学生不存在"
}
```

---

### 场景 4：纯操作无返回（如批量删除）

```python
# 用 str 或 dict 作为泛型参数
@router.post("/batch-delete", response_model=Response[dict])
def batch_delete(...):
    count = dao.batch_delete(ids)
    return Response[dict](
        code=200,
        message="批量删除成功",
        data={"deleted_count": count}  # 包装成字典
    )
```

响应：
```json
HTTP 200 OK
{
    "code": 200,
    "message": "批量删除成功",
    "data": {
        "deleted_count": 5
    }
}
```

---

## 四、错误处理规范

### 错误时抛 HTTPException，不手动包装

```python
# ✅ 正确：抛异常，让 FastAPI 处理 HTTP 状态码
if student is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,  # 真实 404
        detail="学生不存在"
    )

# ❌ 错误：手动返回 200 + code 404
if student is None:
    return Response[Student](
        code=404,           # 业务码 404
        message="学生不存在",
        data=None
    )  # 这样 HTTP 状态码是 200，不规范！
```

### 常用 HTTP 状态码

| 场景 | HTTP 码 | 用法 |
|------|---------|------|
| 成功创建 | 201 | `status.HTTP_201_CREATED` |
| 成功查询/更新/删除 | 200 | `status.HTTP_200_OK` |
| 参数错误 | 400 | `status.HTTP_400_BAD_REQUEST` |
| 资源不存在 | 404 | `status.HTTP_404_NOT_FOUND` |
| 服务器错误 | 500 | `status.HTTP_500_INTERNAL_SERVER_ERROR` |

---

## 五、开发 checklist

写新接口时对照检查：

- [ ] 定义了 `response_model=Response[具体类型]`？
- [ ] `data` 字段用 `XXX.model_validate(orm_obj)` 转换了？
- [ ] 错误时用 `raise HTTPException(...)` 而不是 `return Response(...)`？
- [ ] 列表查询用了 `StudentList` 包装，不是直接 `List[Student]`？
- [ ] 响应体只有 `code` `message` `data` 三个顶层字段？

---

## 六、快速参考模板

### 创建单个资源
```python
@router.post("/", response_model=Response[Student], status_code=201)
def create(...):
    obj = dao.create(...)
    return Response[Student](code=201, message="创建成功", data=Student.model_validate(obj))
```

### 查询单个资源
```python
@router.get("/{id}", response_model=Response[Student])
def get_one(id: int, ...):
    obj = dao.get(id)
    if not obj:
        raise HTTPException(404, "不存在")
    return Response[Student](code=200, message="查询成功", data=Student.model_validate(obj))
```

### 查询列表
```python
@router.get("/", response_model=Response[StudentList])
def get_list(...):
    objs = dao.get_list(...)
    return Response[StudentList](
        code=200, 
        message="查询成功", 
        data=StudentList(list=[Student.model_validate(o) for o in objs], total=len(objs))
    )
```

### 更新
```python
@router.put("/{id}", response_model=Response[Student])
def update(id: int, ...):
    obj = dao.update(id, ...)
    if not obj:
        raise HTTPException(404, "不存在")
    return Response[Student](code=200, message="更新成功", data=Student.model_validate(obj))
```

### 删除
```python
@router.delete("/{id}", response_model=Response[Student])
def delete(id: int, ...):
    obj = dao.delete(id)
    if not obj:
        raise HTTPException(404, "不存在")
    return Response[Student](code=200, message="删除成功", data=Student.model_validate(obj))
```
```

这份文档涵盖了泛型的通俗解释、具体使用示例以及清晰的项目响应规范，可以直接用于团队内部约定。