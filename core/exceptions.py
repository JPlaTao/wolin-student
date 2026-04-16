"""
自定义异常类
为系统提供统一的异常处理体系
"""
from typing import Optional, Any
from enum import Enum


class ErrorCode(str, Enum):
    """错误码枚举"""
    
    # 通用错误码 (1000-1999)
    SUCCESS = "0000"
    INTERNAL_ERROR = "1000"
    INVALID_REQUEST = "1001"
    METHOD_NOT_ALLOWED = "1002"
    
    # 业务错误码 (2000-2999)
    BUSINESS_ERROR = "2000"
    VALIDATION_ERROR = "2001"
    NOT_FOUND = "2002"
    CONFLICT = "2003"
    
    # 认证授权错误码 (3000-3999)
    UNAUTHORIZED = "3000"
    FORBIDDEN = "3001"
    TOKEN_EXPIRED = "3002"
    TOKEN_INVALID = "3003"
    USER_NOT_ACTIVE = "3004"
    
    # 数据库错误码 (4000-4999)
    DATABASE_ERROR = "4000"
    DUPLICATE_KEY = "4001"
    FOREIGN_KEY_ERROR = "4002"
    
    # 外部服务错误码 (5000-5999)
    EXTERNAL_SERVICE_ERROR = "5000"


class AppException(Exception):
    """
    应用基础异常类
    所有自定义异常的基类
    """
    
    def __init__(
        self,
        message: str,
        code: str = ErrorCode.INTERNAL_ERROR.value,
        status_code: int = 500,
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail or message
        self.extra = extra or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "extra": self.extra
        }


class BusinessException(AppException):
    """业务逻辑异常"""
    
    def __init__(
        self,
        message: str = "业务操作失败",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.BUSINESS_ERROR.value,
            status_code=400,
            detail=detail,
            extra=extra
        )


class ValidationException(AppException):
    """参数验证异常"""
    
    def __init__(
        self,
        message: str = "参数验证失败",
        field: Optional[str] = None,
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        if field:
            extra = {**(extra or {}), "field": field}
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR.value,
            status_code=422,
            detail=detail,
            extra=extra
        )


class NotFoundException(AppException):
    """资源未找到异常"""
    
    def __init__(
        self,
        message: str = "资源不存在",
        resource: Optional[str] = None,
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        if resource:
            message = f"{resource}不存在"
            extra = {**(extra or {}), "resource": resource}
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND.value,
            status_code=404,
            detail=detail,
            extra=extra
        )


class ConflictException(AppException):
    """冲突异常"""
    
    def __init__(
        self,
        message: str = "资源冲突",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT.value,
            status_code=409,
            detail=detail,
            extra=extra
        )


class UnauthorizedException(AppException):
    """未认证异常"""
    
    def __init__(
        self,
        message: str = "未认证",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED.value,
            status_code=401,
            detail=detail,
            extra=extra
        )


class ForbiddenException(AppException):
    """权限不足异常"""
    
    def __init__(
        self,
        message: str = "权限不足",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN.value,
            status_code=403,
            detail=detail,
            extra=extra
        )


class TokenExpiredException(AppException):
    """Token过期异常"""
    
    def __init__(
        self,
        message: str = "Token已过期",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.TOKEN_EXPIRED.value,
            status_code=401,
            detail=detail,
            extra=extra
        )


class TokenInvalidException(AppException):
    """Token无效异常"""
    
    def __init__(
        self,
        message: str = "Token无效",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.TOKEN_INVALID.value,
            status_code=401,
            detail=detail,
            extra=extra
        )


class DatabaseException(AppException):
    """数据库操作异常"""
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.DATABASE_ERROR.value,
            status_code=500,
            detail=detail,
            extra=extra
        )


class DuplicateKeyException(AppException):
    """重复键异常"""
    
    def __init__(
        self,
        message: str = "数据已存在",
        field: Optional[str] = None,
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        if field:
            message = f"{field}已存在"
            extra = {**(extra or {}), "field": field}
        super().__init__(
            message=message,
            code=ErrorCode.DUPLICATE_KEY.value,
            status_code=409,
            detail=detail,
            extra=extra
        )


class ExternalServiceException(AppException):
    """外部服务异常"""
    
    def __init__(
        self,
        message: str = "外部服务调用失败",
        service: Optional[str] = None,
        detail: Optional[str] = None,
        extra: Optional[dict] = None
    ):
        if service:
            message = f"{service}调用失败"
            extra = {**(extra or {}), "service": service}
        super().__init__(
            message=message,
            code=ErrorCode.EXTERNAL_SERVICE_ERROR.value,
            status_code=502,
            detail=detail,
            extra=extra
        )
