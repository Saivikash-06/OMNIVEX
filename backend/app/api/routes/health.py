import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_settings
from backend.app.core.config import Settings
from backend.app.database.models import utc_now

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    timestamp: datetime.datetime
    environment: str = "research"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Check backend API status, application version, database connectivity, and current UTC server time.",
)
def get_health(
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_current_settings),
) -> HealthResponse:
    # Verify DB connectivity
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=cfg.VERSION,
        database=db_status,
        timestamp=utc_now(),
        environment="research",
    )
