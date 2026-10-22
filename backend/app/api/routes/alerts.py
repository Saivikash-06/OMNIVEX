from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_api_key
from backend.app.core.errors import NotFoundError
from backend.app.database.models import AlertModel
from backend.app.schemas.alert import AcknowledgeAlertRequest, AlertResponse
from backend.app.schemas.common import AlertSeverityEnum, PaginatedResponse
from backend.app.services.alert_service import acknowledge_alert

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def alert_model_to_response(a: AlertModel) -> AlertResponse:
    return AlertResponse(
        alert_id=a.alert_id,
        run_id=a.run_id,
        timestamp=a.timestamp,
        alert_type=a.alert_type,
        severity=AlertSeverityEnum(a.severity),
        affected_feature_or_metric=a.affected_feature_or_metric,
        explanation=a.explanation,
        evidence=a.evidence,
        suggested_steps=a.suggested_steps,
        acknowledged=a.acknowledged,
        acknowledged_at=a.acknowledged_at,
        acknowledged_by=a.acknowledged_by,
    )


@router.get(
    "",
    response_model=PaginatedResponse[AlertResponse],
    summary="List and Filter Alerts",
    description="Retrieve paginated alerts with filters for severity, type, acknowledgement, and monitoring run.",
    dependencies=[Depends(require_api_key)],
)
def list_alerts(
    severity: Optional[AlertSeverityEnum] = Query(None, description="Filter by alert severity"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    run_id: Optional[str] = Query(None, description="Filter by monitoring run ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AlertResponse]:
    query = db.query(AlertModel)

    if severity:
        query = query.filter(AlertModel.severity == severity.value)
    if alert_type:
        query = query.filter(AlertModel.alert_type == alert_type)
    if acknowledged is not None:
        query = query.filter(AlertModel.acknowledged == acknowledged)
    if run_id:
        query = query.filter(AlertModel.run_id == run_id)

    total = query.count()
    records = query.order_by(AlertModel.timestamp.desc()).offset(offset).limit(limit).all()
    items = [alert_model_to_response(a) for a in records]

    return PaginatedResponse[AlertResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge Alert",
    description="Mark an alert as acknowledged. Action is idempotent.",
    dependencies=[Depends(require_api_key)],
)
def acknowledge_alert_endpoint(
    alert_id: str,
    body: Optional[AcknowledgeAlertRequest] = None,
    db: Session = Depends(get_db),
) -> AlertResponse:
    by = body.acknowledged_by if body else None
    alert = acknowledge_alert(db, alert_id, by)
    return alert_model_to_response(alert)
