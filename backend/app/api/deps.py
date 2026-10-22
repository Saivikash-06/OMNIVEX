from typing import Generator, Optional
from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.config import Settings, settings
from backend.app.core.errors import AuthenticationError
from backend.app.core.security import verify_api_key_constant_time
from backend.app.database.connection import get_db


def get_current_settings() -> Settings:
    """Dependency returning application settings."""
    return settings


def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> None:
    """Verifies API key if OMNIVEX_API_KEY is configured in settings."""
    if settings.OMNIVEX_API_KEY:
        if not x_api_key or not verify_api_key_constant_time(x_api_key, settings.OMNIVEX_API_KEY):
            raise AuthenticationError("Invalid or missing X-API-Key header.")
