import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field
from backend.app.schemas.common import AlertSeverityEnum, StrictBaseModel


class AlertResponse(StrictBaseModel):
    alert_id: str
    run_id: Optional[str] = None
    timestamp: datetime.datetime
    alert_type: str
    severity: AlertSeverityEnum
    affected_feature_or_metric: str
    explanation: str
    evidence: Dict[str, Any]
    suggested_steps: List[str]
    acknowledged: bool
    acknowledged_at: Optional[datetime.datetime] = None
    acknowledged_by: Optional[str] = None


class AcknowledgeAlertRequest(StrictBaseModel):
    acknowledged_by: Optional[str] = Field(None, max_length=100)


class AlertFilterParams(StrictBaseModel):
    severity: Optional[AlertSeverityEnum] = None
    alert_type: Optional[str] = None
    acknowledged: Optional[bool] = None
    run_id: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
