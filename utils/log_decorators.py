"""
日志装饰器工具
用于统一处理API函数的业务日志记录
"""
import functools
import inspect
import logging
from typing import Callable, Any
from fastapi import Request
from utils.logger import get_logger

logger = get_logger("api_logger")


def log_api_call(operation_name: str = None):
    """
    API调用日志装饰器
    
    自动记录API调用的开始、成功、失败日志，并自动处理request_id
    
    Args:
        operation_name: 操作名称，如果为None则使用函数名
    
    Usage:
        @log_api_call("创建学生")
        def create_student(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 获取函数名作为默认操作名称
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 从kwargs中提取Request对象
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )
            
            # 获取request_id
            request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'
            
            # 提取关键参数信息
            params_info = _extract_params_info(func, args, kwargs)
            
            # 记录开始日志
            logger.info(f"[{request_id}] {op_name}开始: {params_info}")
            
            try:
                # 执行原函数
                result = await func(*args, **kwargs)
                
                # 记录成功日志
                logger.info(f"[{request_id}] {op_name}成功")
                return result
                
            except Exception as e:
                # 记录失败日志
                logger.error(f"[{request_id}] {op_name}失败: {str(e)}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 从kwargs中提取Request对象
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )
            
            # 获取request_id
            request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'
            
            # 提取关键参数信息
            params_info = _extract_params_info(func, args, kwargs)
            
            # 记录开始日志
            logger.info(f"[{request_id}] {op_name}开始: {params_info}")
            
            try:
                # 执行原函数
                result = func(*args, **kwargs)
                
                # 记录成功日志
                logger.info(f"[{request_id}] {op_name}成功")
                return result
                
            except Exception as e:
                # 记录失败日志
                logger.error(f"[{request_id}] {op_name}失败: {str(e)}")
                raise
        
        # 根据函数是否为协程函数选择对应的包装器
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def _extract_params_info(func: Callable, args: tuple, kwargs: dict) -> str:
    """
    提取函数参数信息用于日志记录
    
    Args:
        func: 函数对象
        args: 位置参数
        kwargs: 关键字参数
    
    Returns:
        参数信息字符串
    """
    try:
        # 获取函数签名
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # 过滤掉不需要记录的参数
        filtered_params = {}
        for key, value in bound_args.arguments.items():
            # 跳过以下参数
            if key in ['request', 'db', 'current_user', 'self', 'cls']:
                continue
            
            # 尝试转换为可读的字符串
            try:
                if hasattr(value, 'model_dump'):  # Pydantic模型
                    filtered_params[key] = value.model_dump(exclude_unset=True)
                elif hasattr(value, 'dict'):  # 旧版Pydantic
                    filtered_params[key] = value.dict(exclude_unset=True)
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    filtered_params[key] = value
                else:
                    # 复杂对象只显示类型
                    filtered_params[key] = f"<{type(value).__name__}>"
            except Exception:
                filtered_params[key] = f"<无法序列化>"
        
        return str(filtered_params) if filtered_params else "无参数"
    
    except Exception as e:
        return f"<参数提取失败: {str(e)}>"


def log_service_call(service_name: str = None):
    """
    服务层调用日志装饰器
    
    用于记录Service层的业务逻辑调用
    
    Args:
        service_name: 服务名称，如果为None则使用函数名
    """
    def decorator(func: Callable) -> Callable:
        # 获取函数名作为默认服务名称
        svc_name = service_name or func.__name__
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.debug(f"[Service] {svc_name}开始执行")
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"[Service] {svc_name}执行成功")
                return result
            except Exception as e:
                logger.error(f"[Service] {svc_name}执行失败: {str(e)}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger.debug(f"[Service] {svc_name}开始执行")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"[Service] {svc_name}执行成功")
                return result
            except Exception as e:
                logger.error(f"[Service] {svc_name}执行失败: {str(e)}")
                raise
        
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def log_dao_operation(operation_name: str = None):
    """
    DAO层数据库操作日志装饰器
    
    用于记录数据库操作
    
    Args:
        operation_name: 操作名称，如果为None则使用函数名
    """
    def decorator(func: Callable) -> Callable:
        # 获取函数名作为默认操作名称
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"[DAO] {op_name}开始")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"[DAO] {op_name}完成")
                return result
            except Exception as e:
                logger.error(f"[DAO] {op_name}失败: {str(e)}")
                raise
        
        return wrapper

    return decorator


def log_sensitive_operation(operation_name: str = None, level: str = "WARNING"):
    """
    敏感操作日志装饰器

    用于记录删除、硬删除、批量更新等敏感操作
    这些操作需要更高的日志等级以便引起重视和进行安全审计

    Args:
        operation_name: 操作名称，如果为None则使用函数名
        level: 日志等级，默认为 "WARNING"
              可选值: "WARNING", "ERROR", "CRITICAL"

    Usage:
        @router.delete("/students/{stu_id}")
        @log_sensitive_operation("删除学生", level="WARNING")
        def delete_student(...):
            ...

        @router.delete("/class/{class_id}")
        @log_sensitive_operation("硬删除班级", level="ERROR")
        def delete_class_hard(..., hard_delete: bool = True):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 获取函数名作为默认操作名称
        op_name = operation_name or func.__name__

        # 验证日志等级
        valid_levels = ["WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            raise ValueError(f"无效的日志等级: {level}, 必须是: {', '.join(valid_levels)}")

        log_level = getattr(logging, level.upper())

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 从kwargs中提取Request对象
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )

            # 获取request_id
            request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'

            # 记录开始日志
            logger.log(
                log_level,
                f"[{request_id}] [敏感操作] {op_name}开始",
                extra={"operation_type": "sensitive", "level": level}
            )

            try:
                # 执行原函数
                result = await func(*args, **kwargs)

                # 记录成功日志
                logger.log(
                    log_level,
                    f"[{request_id}] [敏感操作] {op_name}成功",
                    extra={"operation_type": "sensitive", "level": level, "status": "success"}
                )
                return result

            except Exception as e:
                # 记录失败日志（总是用ERROR级别）
                logger.error(
                    f"[{request_id}] [敏感操作] {op_name}失败: {str(e)}",
                    extra={"operation_type": "sensitive", "level": level, "status": "failed"}
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 从kwargs中提取Request对象
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )

            # 获取request_id
            request_id = getattr(request.state, 'request_id', 'unknown') if request else 'unknown'

            # 记录开始日志
            logger.log(
                log_level,
                f"[{request_id}] [敏感操作] {op_name}开始",
                extra={"operation_type": "sensitive", "level": level}
            )

            try:
                # 执行原函数
                result = func(*args, **kwargs)

                # 记录成功日志
                logger.log(
                    log_level,
                    f"[{request_id}] [敏感操作] {op_name}成功",
                    extra={"operation_type": "sensitive", "level": level, "status": "success"}
                )
                return result

            except Exception as e:
                # 记录失败日志（总是用ERROR级别）
                logger.error(
                    f"[{request_id}] [敏感操作] {op_name}失败: {str(e)}",
                    extra={"operation_type": "sensitive", "level": level, "status": "failed"}
                )
                raise

        # 根据函数是否为协程函数选择对应的包装器
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def log_mass_operation(operation_name: str = None):
    """
    批量操作日志装饰器

    用于记录批量操作，如批量删除、批量更新等

    Args:
        operation_name: 操作名称

    Usage:
        @router.post("/students/batch-delete")
        @log_mass_operation("批量删除学生")
        def batch_delete_students(student_ids: List[int]):
            ...
    """
    return log_sensitive_operation(operation_name, level="ERROR")
