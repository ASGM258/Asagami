"""
业务异常与全局异常处理

错误码字符串与重构前保持一致，前端 src/api/chat.ts 的 mapErrorCode 依赖它们：

    MISSING_PARAMETER / EMPTY_QUESTION / EMPTY_TITLE / SESSION_NOT_FOUND
    SESSION_CREATE_FAILED / SESSION_UPDATE_FAILED / SESSION_DELETE_FAILED
    AI_SERVICE_ERROR / INTERNAL_SERVER_ERROR / SERVICE_UNAVAILABLE
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import error_response


class BusinessError(Exception):
    """业务异常：携带前端可识别的错误码与 HTTP 状态码"""

    def __init__(
        self,
        message: str,
        error_code: str = "INVALID_REQUEST",
        http_status: int = 400,
        extra_data=None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.extra_data = extra_data


class MissingParameterError(BusinessError):
    """缺少必要参数"""

    def __init__(self, parameter: str) -> None:
        super().__init__(
            message=f"缺少必要参数：{parameter}",
            error_code="MISSING_PARAMETER",
            http_status=400,
        )


class SessionNotFoundError(BusinessError):
    """会话不存在或已被删除"""

    def __init__(self, message: str = "会话不存在或已被删除") -> None:
        super().__init__(
            message=message,
            error_code="SESSION_NOT_FOUND",
            http_status=404,
        )


class AiServiceError(BusinessError):
    """AI 服务调用失败"""

    def __init__(self, message: str, extra_data=None) -> None:
        super().__init__(
            message=message,
            error_code="AI_SERVICE_ERROR",
            http_status=500,
            extra_data=extra_data,
        )


class SessionCreateFailedError(BusinessError):
    """会话创建失败"""

    def __init__(self, message: str = "创建会话失败") -> None:
        super().__init__(
            message=message,
            error_code="SESSION_CREATE_FAILED",
            http_status=500,
        )


class ServiceUnavailableError(BusinessError):
    """
    依赖的服务/数据库尚未就绪

    用于降级场景：例如 PostgreSQL 未启动时会话与问答接口不可用，
    但资讯（走 MySQL）等其它接口应继续可用。
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            http_status=503,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(BusinessError)
    async def handle_business_error(request: Request, exc: BusinessError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_response(exc.message, exc.error_code, exc.extra_data),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic 校验失败：映射为旧版的 MISSING_PARAMETER 语义"""
        return JSONResponse(
            status_code=400,
            content=error_response(
                message="请求参数校验失败",
                error_code="MISSING_PARAMETER",
                extra_data={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """404 / 405 等框架级异常也使用统一响应体"""
        code_map = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            503: "SERVICE_UNAVAILABLE",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                message=str(exc.detail),
                error_code=code_map.get(exc.status_code, "INVALID_REQUEST"),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """兜底异常：与旧版 `服务器内部错误: {e}` 文案保持一致"""
        return JSONResponse(
            status_code=500,
            content=error_response(
                message=f"服务器内部错误: {exc}",
                error_code="INTERNAL_SERVER_ERROR",
            ),
        )
