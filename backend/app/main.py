from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import logger, RequestLoggingMiddleware
from backend.app.core.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
    rate_limit_error_handler,
    unhandled_exception_handler,
)
from backend.app.database.connection import init_db
from backend.app.api.routes import health


# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces basic security headers on every response."""
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for application startup and shutdown."""
    logger.info("Initializing OMNIVEX backend directories and database...")
    # Ensure required directories exist safely
    for directory in [
        settings.DATA_DIR,
        settings.UPLOAD_DIR,
        settings.MODEL_DIR,
        settings.RESULTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
    
    # Initialize database tables
    init_db()
    logger.info("OMNIVEX backend initialized successfully.")
    yield
    logger.info("OMNIVEX backend shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url="/api/openapi.json" if settings.DOCS_ENABLED else None,
        docs_url="/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    # Attach rate limiter to app state
    app.state.limiter = limiter

    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Logging & Request ID Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Exception Handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Register Routers
    app.include_router(health.router, prefix=settings.API_V1_STR)
    from backend.app.api.routes import alerts, datasets, experiments, models, monitoring
    app.include_router(datasets.router, prefix=settings.API_V1_STR)
    app.include_router(models.router, prefix=settings.API_V1_STR)
    app.include_router(monitoring.router, prefix=settings.API_V1_STR)
    app.include_router(alerts.router, prefix=settings.API_V1_STR)
    app.include_router(experiments.router, prefix=settings.API_V1_STR)

    return app


app = create_app()
