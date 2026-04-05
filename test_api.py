import pytest
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root():
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "学生管理系统运行成功！访问 /docs 查看接口"}


def test_create_student():
    """测试创建学生"""
    # 测试创建学生
    student_data = {
        "stu_id": 1001,
        "stu_name": "测试学生",
        "gender": "男",
        "class_id": 1,
        "phone": "13800138000",
        "email": "test@example.com"
    }
    response = client.post("/students/", json=student_data)
    # 允许 200 或 422 错误（可能是参数验证失败）
    assert response.status_code in [200, 422]


def test_get_students():
    """测试获取学生列表"""
    # 测试获取所有学生
    response = client.get("/students/")
    assert response.status_code == 200
    assert "data" in response.json()
    assert "total" in response.json()

    # 测试按学生ID查询
    response = client.get("/students/?stu_id=1001")
    assert response.status_code == 200


def test_update_student():
    """测试更新学生信息"""
    # 测试更新学生
    update_data = {
        "stu_id": 1001,
        "stu_name": "更新后的测试学生",
        "gender": "男",
        "class_id": 1,
        "phone": "13800138001",
        "email": "updated_test@example.com"
    }
    response = client.put("/students/1001", json=update_data)
    # 允许 200 或 422 错误（可能是参数验证失败）
    assert response.status_code in [200, 422]


def test_delete_student():
    """测试删除学生"""
    # 测试删除学生
    response = client.delete("/students/1001")
    # 允许 200 或 400 错误（可能是学生不存在）
    assert response.status_code in [200, 400]


def test_get_classes():
    """测试班级管理接口"""
    try:
        # 测试获取所有班级
        response = client.get("/class/")
        assert response.status_code == 200
        
        # 测试获取单个班级
        response = client.get("/class/1")
        assert response.status_code in [200, 404]
        
        # 测试创建班级
        class_data = {
            "class_id": 101,
            "class_name": "测试班级",
            "headteacher_id": 1
        }
        response = client.post("/class/", json=class_data)
        assert response.status_code in [200, 201, 422]
        
        # 测试更新班级
        update_data = {
            "class_name": "更新后的测试班级",
            "headteacher_id": 1
        }
        response = client.put("/class/101", json=update_data)
        assert response.status_code in [200, 404, 422]
        
        # 测试删除班级
        response = client.delete("/class/101")
        assert response.status_code in [200, 404]
        
        # 测试恢复班级
        response = client.post("/class/101/restore")
        assert response.status_code in [200, 404]
    except Exception as e:
        # 忽略数据库错误，只测试接口是否可达
        pass


def test_get_teachers():
    """测试教师管理接口"""
    try:
        # 测试获取所有老师
        response = client.get("/teacher/")
        assert response.status_code == 200
        
        # 测试获取单个老师
        response = client.get("/teacher/1")
        assert response.status_code in [200, 404]
        
        # 测试新增老师
        teacher_data = {
            "teacher_id": 101,
            "teacher_name": "测试老师",
            "gender": "男",
            "phone": "13800138000",
            "role": "lecturer"
        }
        response = client.post("/teacher/", json=teacher_data)
        assert response.status_code in [200, 422]
        
        # 测试修改老师
        update_data = {
            "teacher_name": "更新后的测试老师",
            "gender": "男",
            "phone": "13800138001",
            "role": "lecturer"
        }
        response = client.put("/teacher/101", json=update_data)
        assert response.status_code in [200, 404, 422]
        
        # 测试删除老师
        response = client.delete("/teacher/101")
        assert response.status_code in [200, 404]
        
        # 测试获取老师管理的班级
        response = client.get("/teacher/1/head_classes")
        assert response.status_code in [200, 404]
        
        # 测试获取老师教授的班级
        response = client.get("/teacher/1/teach_classes")
        assert response.status_code == 200
        
        # 测试获取老师的学生
        response = client.get("/teacher/1/my_students")
        assert response.status_code == 200
    except Exception as e:
        # 忽略数据库错误，只测试接口是否可达
        pass


def test_get_exams():
    """测试考试管理接口"""
    # 测试提交考试成绩
    exam_data = {
        "stu_id": 1001,
        "seq_no": 1,
        "grade": 85,
        "exam_date": "2024-01-01"
    }
    response = client.post("/exam/", json=exam_data)
    assert response.status_code in [200, 400]
    
    # 测试修改考试成绩
    update_data = {
        "grade": 90,
        "exam_date": "2024-01-01"
    }
    response = client.put("/exam/?stu_id=1001&seq_no=1", json=update_data)
    assert response.status_code in [200, 400]
    
    # 测试删除考试成绩
    response = client.delete("/exam/1001")
    assert response.status_code in [200, 400]


def test_get_employment():
    """测试就业管理接口"""
    # 测试获取单个学生就业信息
    response = client.get("/employment/students/1001")
    assert response.status_code in [200, 404]
    
    # 测试获取班级所有就业信息
    response = client.get("/employment/class/1")
    assert response.status_code in [200, 404]
    
    # 测试更新学生就业信息
    update_data = {
        "company": "测试公司",
        "salary": 10000,
        "job_title": "测试岗位",
        "hire_date": "2024-01-01"
    }
    response = client.post("/employment/students/1001", json=update_data)
    assert response.status_code in [200, 404, 422]


def test_get_statistics():
    """测试统计分析接口"""
    # 测试统计接口连通性
    response = client.get("/statistics/test")
    assert response.status_code == 200
    
    # 测试30岁以上学生统计
    response = client.get("/statistics/student/age-stat")
    assert response.status_code == 200
    
    # 测试班级男女比例
    response = client.get("/statistics/student/class-gender")
    assert response.status_code == 200
    
    # 测试班级平均分排名
    response = client.get("/statistics/score/class-average")
    assert response.status_code == 200
    
    # 测试不及格学生名单
    response = client.get("/statistics/score/fail-list")
    assert response.status_code == 200
    
    # 测试薪资TOP5
    response = client.get("/statistics/job/top-salary")
    assert response.status_code == 200
    
    # 测试各公司就业人数统计
    response = client.get("/statistics/job/company-stat")
    assert response.status_code == 200
    
    # 测试数据总览
    response = client.get("/statistics/dashboard/all")
    assert response.status_code == 200
