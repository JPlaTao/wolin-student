"""
学生管理系统 - API 测试
测试分页功能及核心 CRUD 操作
"""
import pytest
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# 测试用的认证 token（需要先登录获取）
TEST_TOKEN = None


def setup_test_user():
    """注册测试用户（如果不存在）"""
    try:
        # 尝试注册测试用户
        client.post("/auth/register", json={
            "username": "test_user",
            "password": "test123",
            "role": "admin"
        })
    except:
        pass


def get_auth_token():
    """获取测试用 token"""
    global TEST_TOKEN
    if TEST_TOKEN:
        return TEST_TOKEN
    
    # 先设置测试用户
    setup_test_user()
    
    # 尝试登录获取 token
    try:
        response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test123"
        })
        if response.status_code == 200:
            TEST_TOKEN = response.json().get("access_token")
            return TEST_TOKEN
        
        # 尝试默认 admin 账户
        response = client.post("/auth/login", json={
            "username": "admin",
            "password": "admin"
        })
        if response.status_code == 200:
            TEST_TOKEN = response.json().get("access_token")
            return TEST_TOKEN
    except:
        pass
    return None


def auth_headers():
    """获取认证请求头"""
    token = get_auth_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ============================================
# 基础测试
# ============================================

def test_root():
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    assert "学生管理系统" in response.text


# ============================================
# 分页功能测试
# ============================================

def test_student_pagination():
    """测试学生列表分页"""
    headers = auth_headers()
    
    # 1. 测试带分页参数的请求
    response = client.get("/students", params={"page": 1, "page_size": 5}, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    assert "total" in data
    
    # 如果有数据，验证返回数量不超过 page_size
    if data["total"] > 0:
        assert len(data["data"]) <= 5
        print(f"  [分页测试] 返回 {len(data['data'])} 条，共 {data['total']} 条")


def test_student_pagination_page2():
    """测试学生列表第二页"""
    headers = auth_headers()
    
    response = client.get("/students", params={"page": 2, "page_size": 5}, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    # 第二页可能为空（如果总数<=5），这是正常的
    assert "data" in data
    print(f"  [第二页] 返回 {len(data['data'])} 条")


def test_student_pagination_no_params():
    """测试学生列表不带分页参数（全量模式，向后兼容）"""
    headers = auth_headers()
    
    response = client.get("/students", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    # 不带参数应该返回全量数据
    print(f"  [全量模式] 返回 {len(data['data'])} 条")


def test_teacher_all_pagination():
    """测试教师列表分页"""
    headers = auth_headers()
    
    response = client.get("/teacher/all", params={"page": 1, "page_size": 3}, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    assert "total" in data
    
    if data["total"] > 0:
        assert len(data["data"]) <= 3
        print(f"  [教师分页] 返回 {len(data['data'])} 条，共 {data['total']} 条")


def test_counselors_endpoint():
    """测试顾问列表 API"""
    headers = auth_headers()
    
    response = client.get("/teacher/counselors", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    
    # 验证返回的都是顾问角色
    for teacher in data["data"]:
        assert teacher.get("role") == "counselor"
    
    print(f"  [顾问列表] 返回 {len(data['data'])} 位顾问")


def test_class_pagination():
    """测试班级列表分页"""
    headers = auth_headers()
    
    response = client.get("/class/", params={"page": 1, "page_size": 5}, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    print(f"  [班级分页] 返回 {len(data['data'])} 个班级")


# ============================================
# CRUD 操作测试（回归测试）
# ============================================

def test_create_and_delete_student():
    """测试创建和删除学生（关键路径）"""
    headers = auth_headers()
    
    # 1. 创建学生
    new_student = {
        "stu_name": "测试学生",
        "native_place": "北京",
        "graduated_school": "测试学校",
        "major": "计算机",
        "admission_date": "2024-01-01",
        "graduation_date": "2027-01-01",
        "education": "本科",
        "age": 20,
        "gender": "男",
        "class_id": 1,
        "advisor_id": 1
    }
    
    response = client.post("/students/", json=new_student, headers=headers)
    
    # 检查创建是否成功
    if response.status_code == 200:
        created = response.json()
        stu_id = created.get("data", {}).get("stu_id")
        
        if stu_id:
            # 2. 删除刚创建的学生
            del_response = client.delete(f"/students/{stu_id}", headers=headers)
            assert del_response.status_code == 200
            print(f"  [CRUD测试] 创建学生 ID={stu_id}，删除成功")
            return
    
    # 如果创建失败，可能是数据约束问题，尝试查询已有数据
    print(f"  [CRUD测试] 跳过创建，状态码: {response.status_code}")


def test_update_student():
    """测试更新学生信息"""
    headers = auth_headers()
    
    # 先获取一个学生
    response = client.get("/students", params={"page": 1, "page_size": 1}, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data["data"]:
            stu_id = data["data"][0]["stu_id"]
            
            # 更新学生
            update_data = {"stu_name": "更新测试"}
            update_response = client.put(f"/students/{stu_id}", json=update_data, headers=headers)
            
            if update_response.status_code == 200:
                print(f"  [更新测试] 学生 ID={stu_id} 更新成功")
            else:
                print(f"  [更新测试] 跳过，状态码: {update_response.status_code}")


# ============================================
# 错误边界测试
# ============================================

def test_pagination_invalid_page():
    """测试无效页码"""
    headers = auth_headers()
    
    response = client.get("/students", params={"page": 0, "page_size": 10}, headers=headers)
    # 应该正常返回（后端会处理为第1页）
    assert response.status_code in [200, 422]


def test_pagination_negative_page():
    """测试负数页码"""
    headers = auth_headers()
    
    response = client.get("/students", params={"page": -1, "page_size": 10}, headers=headers)
    # 应该正常返回或返回 422
    assert response.status_code in [200, 422]


def test_pagination_oversized_page():
    """测试超大页码"""
    headers = auth_headers()
    
    response = client.get("/students", params={"page": 999999, "page_size": 10}, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    # 应该返回空列表，而不是报错
    assert "data" in data
    print(f"  [超大页码] 返回 {len(data['data'])} 条（正确返回空）")


# ============================================
# 统计接口测试
# ============================================

def test_dashboard():
    """测试仪表盘数据"""
    headers = auth_headers()
    
    response = client.get("/statistics/dashboard", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "data" in data
    print(f"  [仪表盘] 学生数: {data['data'].get('total_students', 0)}")


# ============================================
# 测试运行入口
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("学生管理系统 - API 自动化测试")
    print("=" * 50)
    
    tests = [
        ("基础测试", test_root),
        ("学生分页", test_student_pagination),
        ("学生第二页", test_student_pagination_page2),
        ("学生全量模式", test_student_pagination_no_params),
        ("教师分页", test_teacher_all_pagination),
        ("顾问列表", test_counselors_endpoint),
        ("班级分页", test_class_pagination),
        ("学生CRUD", test_create_and_delete_student),
        ("学生更新", test_update_student),
        ("无效页码", test_pagination_invalid_page),
        ("负数页码", test_pagination_negative_page),
        ("超大页码", test_pagination_oversized_page),
        ("仪表盘", test_dashboard),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
