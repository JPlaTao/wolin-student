"""教师工具 Pydantic 请求/响应 Schema"""
from pydantic import BaseModel, Field


class PolishNoticeRequest(BaseModel):
    """公告润色请求"""
    text: str = Field(..., min_length=1, description="通知草稿")
    style: str = Field(default="formal", description="formal | humorous | warm")


class PolishNoticeResponse(BaseModel):
    """公告润色响应"""
    polished: str


class DiagnoseScoreRequest(BaseModel):
    """成绩诊断请求"""
    stu_id: int


class ExamRecordItem(BaseModel):
    """单次考试成绩条目"""
    seq_no: int
    grade: float
    exam_date: str


class DiagnoseScoreResponse(BaseModel):
    """成绩诊断响应"""
    stu_name: str
    class_name: str
    exam_records: list[ExamRecordItem]
    analysis: str


class GenerateCommentRequest(BaseModel):
    """评语生成请求"""
    keywords: str = Field(..., min_length=1)


class GenerateCommentResponse(BaseModel):
    """评语生成响应"""
    comment: str
