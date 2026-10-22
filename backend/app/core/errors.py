import uuid
import logging
from typing import Any, List, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger("omnivex")


class AppError(Exception):
    """Base application exception with unified structure."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppError):
    def __init__(self, message: str, details: Optional[List[Any]] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "Payload exceeds maximum allowed size"):
        super().__init__(
            code="PAYLOAD_TOO_LARGE",
            message=message,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


class UnsupportedMediaTypeError(AppError):
    def __init__(self, message: str = "Unsupported media type. Only .csv files are permitted"):
        super().__init__(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=message,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )


class ValidationAppError(AppError):
    def __init__(self, message: str, details: Optional[List[Any]] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid or missing API key"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class SecurityViolationError(AppError):
    def __init__(self, message: str = "Security validation failed"):
        super().__init__(
            code="SECURITY_VIOLATION",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class MonitoringError(AppError):
    def __init__(self, message: str, details: Optional[List[Any]] = None):
        super().__init__(
            code="MONITORING_ERROR",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


def format_error_response(code: str, message: str, details: Optional[List[Any]] = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc.code, exc.message, exc.details),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        details.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=format_error_response(
            code="VALIDATION_ERROR",
            message="Request body or query parameter validation failed.",
            details=details,
        ),
    )


async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=format_error_response(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded: {exc.detail}",
            details=[],
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(
        f"Internal server error for request_id={req_id}: {exc}",
        exc_info=True,
        extra={"request_id": req_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            code="INTERNAL_SERVER_ERROR",
            message=f"An unexpected server error occurred. Correlation ID: {req_id}",
            details=[],
        ),
    )
