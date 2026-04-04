# Wolin Students Education Management System

A comprehensive education management system built on FastAPI and SQLAlchemy, providing RESTful API interfaces for core functionalities such as student, class, teacher, employment, and exam management.

## Project Overview

Wolin Students is an information management system designed for educational institutions, adopting a frontend-backend separation architecture. The backend is built using the Python FastAPI framework to deliver RESTful APIs, combined with SQLAlchemy for database operations. The system supports functionalities including student information management, class management, teacher management, employment tracking, exam score management, and data analytics.

## Technology Stack

- **Web Framework**: FastAPI
- **Database ORM**: SQLAlchemy
- **Database**: MySQL
- **Data Validation**: Pydantic
- **Python Version**: 3.x

## Functional Modules

### 1. Student Management (Student API)
- Retrieve student list (supports filtering by student ID, name, class)
- Create new student
- Update student information
- Delete student

### 2. Class Management (Class API)
- Retrieve all classes
- Retrieve single class information
- Create class
- Update class information
- Delete class

### 3. Teacher Management (Teacher API)
- Retrieve teacher list
- Retrieve teacher information
- Create teacher
- Update teacher information
- Delete teacher
- Query classes taught by a teacher
- Query classes where a teacher serves as homeroom teacher
- Query students under a teacher’s employment guidance

### 4. Employment Management (Employment API)
- Query employment records (supports multi-condition filtering)
- Update employment information
- Delete employment record

### 5. Exam Management (Exam API)
- Submit exam scores

### 6. Statistics & Analytics (Statistics API)
- Count of students over 30 years old
- Gender ratio by class
- Class average score ranking
- List of failing students
- Top 5 salary earners
- Employment count by company
- Comprehensive data dashboard

## Project Structure

```
WolinStudents/
├── api/                    # API routing layer
│   ├── class_api.py       # Class management interface
│   ├── employment_api.py  # Employment management interface
│   ├── exam_api.py        # Exam management interface
│   ├── statistics_api.py  # Statistics and analytics interface
│   ├── student_api.py     # Student management interface
│   └── teacher_api.py     # Teacher management interface
├── dao/                   # Data access layer
│   ├── class_dao.py
│   ├── employment_dao.py
│   ├── exam_dao.py
│   ├── student_dao.py
│   └── teacher_dao.py
├── model/                 # Database models
│   ├── class_model.py
│   ├── employment.py
│   ├── exam_model.py
│   ├── student.py
│   └── teachers.py
├── schemas/               # Pydantic data models
│   ├── class_schemas.py
│   ├── exam_request.py
│   ├── response.py
│   └── stu_request.py
├── database.py            # Database configuration
├── main.py                # Application entry point
├── requirements.txt       # Dependency packages
└── wolin_test1.sql        # Database initialization script
```

## Quick Start

### Prerequisites

- Python 3.7+
- MySQL 5.7+

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Database

Modify the database connection settings in `database.py` according to your environment.

### Initialize Database

```bash
mysql -u root -p
```