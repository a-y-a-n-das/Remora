from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, status_code=400, details=details)


class NotFoundError(AppException):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, status_code=404, details=details)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Unauthorized", details: dict = None):
        super().__init__(message, status_code=401, details=details)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Forbidden", details: dict = None):
        super().__init__(message, status_code=403, details=details)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded", details: dict = None):
        super().__init__(message, status_code=429, details=details)


async def app_exception_handler(request: Request, exc: AppException):
    logger.error(
        "app_exception",
        path=request.url.path,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "details": exc.details},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )