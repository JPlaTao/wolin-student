import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from utils.logger import get_logger

logger = get_logger("middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    日志记录中间件
    记录所有 HTTP 请求的详细信息，包括请求方法、URL、响应时间、状态码等
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求 ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # 记录请求开始时间
        start_time = time.time()

        # 获取请求信息
        method = request.method
        url = str(request.url)
        client_host = request.client.host if request.client else "unknown"

        # 记录请求信息
        logger.info(f"[{request_id}] Request started: {method} {url} from {client_host}")

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录响应信息
            status_code = response.status_code
            logger.info(
                f"[{request_id}] Request completed: {method} {url} "
                f"- Status: {status_code} - Time: {process_time:.3f}s"
            )

            # 添加请求 ID 到响应头
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录异常信息
            logger.error(
                f"[{request_id}] Request failed: {method} {url} "
                f"- Error: {str(e)} - Time: {process_time:.3f}s",
                exc_info=True
            )
            raise


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    错误日志记录中间件
    专门用于捕获和记录异常信息
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            request_id = getattr(request.state, 'request_id', 'unknown')
            logger.error(
                f"[{request_id}] Unhandled exception in {request.method} {request.url}: {str(e)}",
                exc_info=True
            )
            raise
