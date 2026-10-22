import logging
import sys
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import uuid

# Configure standard structured logger
logger = logging.getLogger("omnivex")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [request_id=%(request_id)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class RequestContextFilter(logging.Filter):
    """Ensures request_id is always present in log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


logger.addFilter(RequestContextFilter())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests with latency and status code.
    Never logs request bodies, DataFrames, or secrets.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        start_time = time.perf_counter()

        # Log entry
        logger.info(
            f"Incoming {request.method} {request.url.path}",
            extra={"request_id": req_id},
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            response.headers["X-Correlation-ID"] = req_id
            logger.info(
                f"Completed {request.method} {request.url.path} -> {response.status_code} in {duration_ms:.2f}ms",
                extra={"request_id": req_id},
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path} after {duration_ms:.2f}ms: {type(exc).__name__}",
                extra={"request_id": req_id},
                exc_info=True,
            )
            raise
