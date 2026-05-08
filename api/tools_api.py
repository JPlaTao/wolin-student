"""教师实用工具 API — 公告润色 / 成绩诊断 / 评语生成"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.permissions import require_role
from schemas.response import ResponseBase
from schemas.tools_schemas import (
    PolishNoticeRequest,
    PolishNoticeResponse,
    DiagnoseScoreRequest,
    DiagnoseScoreResponse,
    ExamRecordItem,
    GenerateCommentRequest,
    GenerateCommentResponse,
)
from services import tools_service
from core.exceptions import NotFoundException
from utils.logger import get_logger

logger = get_logger("tools_api")

router = APIRouter(prefix="/tools", tags=["教师工具"])


@router.post("/polish-notice")
async def polish_notice(
    req: PolishNoticeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "teacher"])),
):
    """公告/通知润色 — 将草稿改写为指定风格的通知"""
    logger.info(f"用户 {current_user.username} 请求公告润色: style={req.style}")
    polished = await tools_service.polish_notice(text=req.text, style=req.style)
    return ResponseBase(code=200, message="success", data=PolishNoticeResponse(polished=polished))


@router.post("/diagnose-score")
async def diagnose_score(
    req: DiagnoseScoreRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "teacher"])),
):
    """成绩波动诊断 — 分析学生历次考试成绩趋势"""
    logger.info(f"用户 {current_user.username} 请求成绩诊断: stu_id={req.stu_id}")
    try:
        stu_name, class_name, exam_records, analysis = await tools_service.diagnose_score(
            stu_id=req.stu_id, db=db
        )
    except NotFoundException:
        raise

    return ResponseBase(
        code=200,
        message="success",
        data=DiagnoseScoreResponse(
            stu_name=stu_name,
            class_name=class_name,
            exam_records=[ExamRecordItem(**r) for r in exam_records],
            analysis=analysis,
        ),
    )


@router.post("/generate-comment")
async def generate_comment(
    req: GenerateCommentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["admin", "teacher"])),
):
    """期末评语生成 — 根据学生特点关键词生成三明治式评语"""
    logger.info(f"用户 {current_user.username} 请求评语生成: keywords={req.keywords}")
    comment = await tools_service.generate_comment(keywords=req.keywords)
    return ResponseBase(code=200, message="success", data=GenerateCommentResponse(comment=comment))
