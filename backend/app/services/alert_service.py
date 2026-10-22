import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import NotFoundError
from backend.app.database.models import AlertModel, utc_now
from backend.app.schemas.alert import AlertResponse
from backend.app.schemas.common import AlertSeverityEnum
from backend.app.schemas.dataset import SchemaValidationIssue
from backend.app.schemas.drift import DriftAnalysisResponse
from backend.app.schemas.performance import PerformanceMetricsDetail, ReliabilityAnalysisResponse


def generate_alerts_from_monitoring(
    db: Session,
    run_id: Optional[str],
    schema_issues: List[SchemaValidationIssue],
    drift_response: Optional[DriftAnalysisResponse],
    perf_metrics: Optional[PerformanceMetricsDetail],
    reliability_response: ReliabilityAnalysisResponse,
) -> List[AlertModel]:
    """Generate capped, prioritized alerts based on monitoring and reliability findings."""
    alerts_to_create: List[AlertModel] = []

    # 1. Schema issues
    for issue in schema_issues:
        sev = AlertSeverityEnum.CRITICAL if issue.category in ("missing_columns", "incompatible_dtypes") else AlertSeverityEnum.WARNING
        alerts_to_create.append(
            AlertModel(
                run_id=run_id,
                alert_type="SCHEMA_MISMATCH",
                severity=sev.value,
                affected_feature_or_metric=issue.column or "dataset",
                explanation=issue.message,
                evidence=issue.details or {},
                suggested_steps=[
                    "Inspect the data ingestion pipeline upstream.",
                    "Verify column naming conventions and data types in the incoming source.",
                    "Confirm the incoming batch matches the reference contract before processing.",
                ],
            )
        )

    # 2. Performance degradation
    if perf_metrics and perf_metrics.degradation_flagged:
        alerts_to_create.append(
            AlertModel(
                run_id=run_id,
                alert_type="PERFORMANCE_DEGRADATION",
                severity=AlertSeverityEnum.CRITICAL.value,
                affected_feature_or_metric="accuracy_and_f1",
                explanation=(
                    f"Model accuracy ({perf_metrics.accuracy}) or F1 ({perf_metrics.f1}) "
                    f"has degraded beyond the allowable tolerance relative to baseline."
                ),
                evidence={
                    "accuracy": perf_metrics.accuracy,
                    "f1": perf_metrics.f1,
                    "abs_diff_accuracy": perf_metrics.abs_diff_accuracy,
                    "abs_diff_f1": perf_metrics.abs_diff_f1,
                    "accuracy_ci": perf_metrics.accuracy_ci.model_dump() if perf_metrics.accuracy_ci else None,
                },
                suggested_steps=[
                    "Collect ground-truth labels for additional recent instances to confirm persistent degradation.",
                    "Analyze confusion matrix to identify specific class confusion patterns.",
                    "Audit input feature distributions for corresponding data drift.",
                    "Review whether retraining or calibration is warranted after thorough offline validation.",
                ],
            )
        )

    # 3. Feature drift alerts
    if drift_response:
        for feat in drift_response.per_feature_results:
            if feat.status.value == "drift":
                # Determine severity: PSI >= major threshold -> critical; drift without labels -> warning
                has_labels = perf_metrics and perf_metrics.status == "evaluated"
                is_major = "PSI=" in feat.note and any(
                    float(part.split("=")[1]) >= settings.PSI_MAJOR
                    for part in feat.note.split(",")
                    if "PSI=" in part
                )
                if is_major and has_labels and perf_metrics.degradation_flagged:
                    sev = AlertSeverityEnum.CRITICAL
                elif is_major:
                    sev = AlertSeverityEnum.WARNING
                else:
                    sev = AlertSeverityEnum.WARNING if not has_labels else AlertSeverityEnum.INFO

                alerts_to_create.append(
                    AlertModel(
                        run_id=run_id,
                        alert_type="FEATURE_DRIFT",
                        severity=sev.value,
                        affected_feature_or_metric=feat.feature,
                        explanation=f"Significant statistical distribution change detected in feature '{feat.feature}'.",
                        evidence={
                            "statistic": feat.statistic,
                            "p_value": feat.p_value,
                            "adjusted_p_value": feat.adjusted_p_value,
                            "threshold": feat.threshold,
                            "test_name": feat.test_name,
                            "note": feat.note,
                        },
                        suggested_steps=[
                            f"Inspect upstream data collection for feature '{feat.feature}'.",
                            "Plot reference vs incoming distributions (histogram or KDE) to observe shift shape.",
                            "Check if domain changes or sensor calibration updates occurred recently.",
                            "Remember: drift indicates distribution change, not confirmed accuracy loss.",
                        ],
                    )
                )

    # 4. Cap alerts if exceeding max per run to avoid flooding
    max_alerts = settings.MAX_ALERTS_PER_RUN
    if len(alerts_to_create) > max_alerts:
        capped_alerts = alerts_to_create[: max_alerts - 1]
        summary_alert = AlertModel(
            run_id=run_id,
            alert_type="ALERT_FLOOD_SUMMARY",
            severity=AlertSeverityEnum.WARNING.value,
            affected_feature_or_metric="multiple_features",
            explanation=(
                f"A total of {len(alerts_to_create)} alerts were triggered during this run. "
                f"Display capped at {max_alerts} to prevent alert fatigue."
            ),
            evidence={"total_alerts": len(alerts_to_create), "capped_to": max_alerts},
            suggested_steps=[
                "Review full monitoring run summary report for global distribution statistics.",
                "Prioritize investigating critical schema and performance alerts first.",
            ],
        )
        capped_alerts.append(summary_alert)
        alerts_to_create = capped_alerts

    # Persist alerts to database
    for a in alerts_to_create:
        db.add(a)
    db.commit()

    return alerts_to_create


def acknowledge_alert(
    db: Session,
    alert_id: str,
    acknowledged_by: Optional[str] = None,
) -> AlertModel:
    """Acknowledge an alert. Idempotent: if already acknowledged, keeps existing timestamp."""
    alert = db.query(AlertModel).filter(AlertModel.alert_id == alert_id).first()
    if not alert:
        raise NotFoundError("Alert", alert_id)

    if not alert.acknowledged:
        alert.acknowledged = True
        alert.acknowledged_at = utc_now()
        alert.acknowledged_by = acknowledged_by or "analyst"
        db.commit()
        db.refresh(alert)

    return alert
