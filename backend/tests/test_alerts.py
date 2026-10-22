import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.database.models import AlertModel
from backend.app.schemas.common import AlertSeverityEnum, MultipleTestingMethodEnum, ReliabilityStateEnum
from backend.app.schemas.dataset import SchemaValidationIssue
from backend.app.schemas.drift import DriftAnalysisResponse, DriftFeatureResult, DriftSummary, DriftStatusEnum
from backend.app.schemas.performance import PerformanceMetricsDetail, ReliabilityAnalysisResponse
from backend.app.services.alert_service import generate_alerts_from_monitoring


def test_alert_generation_and_capping(db_session: Session):
    schema_issues = [
        SchemaValidationIssue(
            category="missing_columns",
            column="col_x",
            message="Required column 'col_x' is missing.",
        )
    ]
    # Create 25 drift features to test capping (max 20 per run)
    drift_features = [
        DriftFeatureResult(
            feature=f"feat_{i}",
            feature_type="numeric",
            test_name="ks",
            statistic=0.45,
            threshold=0.05,
            status=DriftStatusEnum.DRIFT,
            reference_n=100,
            incoming_n=100,
            note="PSI=0.30",
        )
        for i in range(25)
    ]
    drift_resp = DriftAnalysisResponse(
        reference_dataset_id="ref",
        incoming_dataset_id="inc",
        per_feature_results=drift_features,
        summary=DriftSummary(
            features_tested=25,
            features_skipped=0,
            features_drifted=25,
            drift_ratio=1.0,
            overall_drift_detected=True,
            multiple_testing_method=MultipleTestingMethodEnum.NONE,
        ),
    )
    rel_resp = ReliabilityAnalysisResponse(
        reliability_state=ReliabilityStateEnum.DRIFT_DETECTED,
        reasons=["Drift detected"],
        drift_detected=True,
        performance_status="labels_unavailable",
        performance_degradation_confirmed=False,
        summary_note="Drift detected",
    )

    created_alerts = generate_alerts_from_monitoring(
        db=db_session,
        run_id=None,
        schema_issues=schema_issues,
        drift_response=drift_resp,
        perf_metrics=None,
        reliability_response=rel_resp,
    )

    # Max alerts per run is capped at 20
    assert len(created_alerts) == 20
    assert any(a.alert_type == "ALERT_FLOOD_SUMMARY" for a in created_alerts)


def test_alert_api_lifecycle(client: TestClient, db_session: Session):
    # Create test alert directly in DB
    alert = AlertModel(
        alert_type="FEATURE_DRIFT",
        severity=AlertSeverityEnum.CRITICAL.value,
        affected_feature_or_metric="customer_age",
        explanation="KS test showed significant shift.",
        evidence={"statistic": 0.35},
        suggested_steps=["Inspect upstream pipeline"],
        acknowledged=False,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    alert_id = alert.alert_id

    # 1. Filter listing by severity
    list_resp = client.get(f"/api/alerts?severity=critical&acknowledged=false")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(a["alert_id"] == alert_id for a in list_data["items"])

    # 2. Acknowledge alert
    ack_resp = client.patch(
        f"/api/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "lead_ml_engineer"},
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["acknowledged"] is True
    assert ack_data["acknowledged_by"] == "lead_ml_engineer"
    first_ack_time = ack_data["acknowledged_at"]
    assert first_ack_time is not None

    # 3. Idempotent re-acknowledgement
    re_ack_resp = client.patch(
        f"/api/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "another_user"},
    )
    assert re_ack_resp.status_code == 200
    re_ack_data = re_ack_resp.json()
    assert re_ack_data["acknowledged_at"] == first_ack_time  # Unchanged timestamp!

    # 4. Unknown alert ID returns 404
    bad_resp = client.patch("/api/alerts/non-existent-alert-id/acknowledge")
    assert bad_resp.status_code == 404
