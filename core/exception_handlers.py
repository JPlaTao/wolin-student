"""
全局异常处理器
统一处理所有异常，返回标准化的错误响应
"""
import traceback
from typing import Any, Dict, Optional, Union
from datetime import datetime
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from jwt.exceptions import PyJWTError

from core.exceptions import (
    AppException,
    BusinessException,
    ValidationException,
    NotFoundException,
    ConflictException,
    UnauthorizedException,
    ForbiddenException,
    TokenExpiredException,
    TokenInvalidException,
    DatabaseException,
    DuplicateKeyException,
    ExternalServiceException
)
from utils.logger import get_logger

logger = get_logger("exception_handler")


class ExceptionHandler:
    """异常处理器类"""
    
    @staticmethod
    def create_error_response(
        request_id: str,
        code: str,
        message: str,
        detail: str,
        status_code: int,
        extra: Optional[dict] = None
    ) -> JSONResponse:
        """
        创建统一的错误响应
        
        Args:
            request_id: 请求ID
            code: 错误码
            message: 错误信息
            detail: 详细错误信息
            status_code: HTTP状态码
            extra: 额外信息
            
        Returns:
            JSONResponse: 标准化的错误响应
        """
        response_data = {
            "code": code,
            "message": message,
            "detail": ExceptionHandler.filter_sensitive_info(detail),
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id
        }
        
        if extra:
            response_data["extra"] = extra
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
    
    @staticmethod
    def filter_sensitive_info(info: str) -> str:
        """
        过滤敏感信息
        
        Args:
            info: 原始信息
            
        Returns:
            过滤后的信息
        """
        if not info:
            return info
        
        # 过滤数据库连接信息
        sensitive_patterns = [
            'password',
            'secret',
            'token',
            'api_key',
            'mysql://',
            'postgresql://',
            'sqlite://',
            'mongodb://',
            'redis://'
        ]
        
        filtered_info = info
        for pattern in sensitive_patterns:
            if pattern.lower() in filtered_info.lower():
                filtered_info = filtered_info.replace(
                    pattern, 
                    f'{pattern[:2]}***'
                )
        
        return filtered_info
    
    @staticmethod
    def log_exception(
        request: Request,
        exception: Exception,
        is_expected: bool = False
    ):
        """
        记录异常日志
        
        Args:
            request: 请求对象
            exception: 异常对象
            is_expected: 是否为预期内的异常
        """
        request_id = getattr(request.state, 'request_id', 'unknown')
        method = request.method
        url = str(request.url)
        
        if is_expected:
            # 预期内的异常，记录为warning
            logger.warning(
                f"[{request_id}] [ExceptionHandler] {method} {url}: "
                f"{type(exception).__name__}: {str(exception)}"
            )
        else:
            # 未预期的异常，记录为error，包含堆栈信息
            logger.error(
                f"[{request_id}] [ExceptionHandler] {method} {url}: "
                f"{type(exception).__name__}: {str(exception)}",
                exc_info=True
            )


# 自定义异常处理器
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理自定义应用异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 记录日志（预期内异常）
    ExceptionHandler.log_exception(request, exc, is_expected=True)
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
        status_code=exc.status_code,
        extra=exc.extra
    )


# 参数验证异常处理器
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求参数验证异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 提取验证错误信息
    errors = exc.errors()
    error_details = []
    
    for error in errors:
        field = '.'.join(str(loc) for loc in error.get('loc', []))
        message = error.get('msg', '验证失败')
        error_details.append(f"{field}: {message}")
    
    error_message = f"参数验证失败: {'; '.join(error_details)}"
    
    # 记录日志
    ExceptionHandler.log_exception(request, exc, is_expected=True)
    
    # 将errors转换为可JSON序列化的格式（处理bytes等不可序列化类型）
    serializable_errors = []
    for error in errors:
        serializable_error = {}
        for key, value in error.items():
            if isinstance(value, bytes):
                serializable_error[key] = value.decode('utf-8', errors='replace')
            elif isinstance(value, (list, tuple)):
                serializable_error[key] = [v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v for v in value]
            else:
                serializable_error[key] = value
        serializable_errors.append(serializable_error)
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code="2001",
        message="参数验证失败",
        detail=error_message,
        status_code=422,
        extra={"errors": serializable_errors}
    )


# Pydantic验证异常处理器
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """处理Pydantic模型验证异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    errors = exc.errors()
    error_message = f"数据验证失败: {errors[0]['msg']}" if errors else "数据验证失败"
    
    # 记录日志
    ExceptionHandler.log_exception(request, exc, is_expected=True)
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code="2001",
        message="数据验证失败",
        detail=error_message,
        status_code=422,
        extra={"errors": errors}
    )


# SQLAlchemy异常处理器
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """处理SQLAlchemy数据库异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 判断是否为完整性错误（重复键、外键约束等）
    if isinstance(exc, IntegrityError):
        error_msg = str(exc.orig)
        if "Duplicate entry" in error_msg or "unique constraint" in error_msg.lower():
            # 重复键错误
            return ExceptionHandler.create_error_response(
                request_id=request_id,
                code="4001",
                message="数据已存在",
                detail="该数据已存在，不能重复创建",
                status_code=409
            )
        elif "foreign key constraint" in error_msg.lower():
            # 外键约束错误
            return ExceptionHandler.create_error_response(
                request_id=request_id,
                code="4002",
                message="数据关联错误",
                detail="关联的数据不存在",
                status_code=400
            )
    
    # 其他数据库错误
    # 记录日志（数据库异常总是需要详细日志）
    ExceptionHandler.log_exception(request, exc, is_expected=False)
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code="4000",
        message="数据库操作失败",
        detail="数据库操作失败，请稍后重试",
        status_code=500
    )


# JWT异常处理器
async def jwt_exception_handler(request: Request, exc: PyJWTError) -> JSONResponse:
    """处理JWT相关异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 记录日志
    ExceptionHandler.log_exception(request, exc, is_expected=True)
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code="3002",
        message="认证失败",
        detail="Token无效或已过期，请重新登录",
        status_code=401
    )


# 通用异常处理器
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理所有未捕获的异常"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 记录详细的异常日志
    ExceptionHandler.log_exception(request, exc, is_expected=False)
    
    # 开发环境显示详细错误，生产环境隐藏
    import os
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    
    if is_debug:
        detail = f"{type(exc).__name__}: {str(exc)}"
    else:
        detail = "服务器内部错误，请稍后重试"
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code="1000",
        message="服务器内部错误",
        detail=detail,
        status_code=500
    )


# FastAPI异常处理器
async def http_exception_handler(request: Request, exc: Any) -> JSONResponse:
    """处理FastAPI HTTPException"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # 提取错误信息
    status_code = getattr(exc, 'status_code', 500)
    detail = getattr(exc, 'detail', 'HTTP错误')
    
    # 记录日志
    ExceptionHandler.log_exception(request, exc, is_expected=True)
    
    # 根据状态码映射错误码
    error_code_map = {
        400: "1001",
        401: "3000",
        403: "3001",
        404: "2002",
        405: "1002",
        422: "2001",
        500: "1000"
    }
    
    code = error_code_map.get(status_code, "1000")
    
    return ExceptionHandler.create_error_response(
        request_id=request_id,
        code=code,
        message="HTTP错误",
        detail=detail,
        status_code=status_code
    )


def register_exception_handlers(app):
    """
    注册所有异常处理器
    
    Args:
        app: FastAPI应用实例
    """
    # 自定义异常
    app.add_exception_handler(AppException, app_exception_handler)
    
    # FastAPI和Pydantic验证异常
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    
    # SQLAlchemy数据库异常
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    
    # JWT异常
    app.add_exception_handler(PyJWTError, jwt_exception_handler)
    
    # FastAPI HTTPException
    try:
        from fastapi import HTTPException
        app.add_exception_handler(HTTPException, http_exception_handler)
    except ImportError:
        pass
    
    # 通用异常（必须最后注册）
    app.add_exception_handler(Exception, general_exception_handler)
