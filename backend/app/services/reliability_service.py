from typing import List, Optional, Tuple
from backend.app.schemas.common import ReliabilityStateEnum
from backend.app.schemas.drift import DriftSummary
from backend.app.schemas.performance import (
    PerformanceMetricsDetail,
    ReliabilityAnalysisResponse,
)


def evaluate_reliability_state(
    drift_summary: Optional[DriftSummary],
    performance_metrics: Optional[PerformanceMetricsDetail],
    schema_valid: bool = True,
    computation_error: Optional[str] = None,
    incoming_sample_count: int = 0,
    min_samples_drift: int = 30,
) -> ReliabilityAnalysisResponse:
    """Evaluate overall AI reliability state strictly adhering to the 6-state decision table.

    Evaluated in exact priority order:
    1. MONITORING_ERROR
    2. INSUFFICIENT_DATA
    3. DRIFT_AND_PERFORMANCE_DEGRADATION
    4. PERFORMANCE_DEGRADATION
    5. DRIFT_DETECTED
    6. NORMAL
    """
    reasons: List[str] = []

    # 1. MONITORING_ERROR
    if computation_error:
        reasons.append(f"A monitoring computation failed: {computation_error}")
        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.MONITORING_ERROR,
            reasons=reasons,
            drift_detected=False,
            performance_status="error",
            performance_degradation_confirmed=False,
            performance_metrics=performance_metrics,
            summary_note="Monitoring calculation encountered an unhandled error; no reliability conclusions can be drawn.",
        )

    # 2. INSUFFICIENT_DATA
    # Condition: schema validation failed in a blocking manner OR (sample count < min_samples AND labels absent/insufficient)
    perf_status = performance_metrics.status if performance_metrics else "not_requested"
    labels_insufficient_or_absent = perf_status in ("insufficient_data", "labels_unavailable", "not_requested")

    if not schema_valid:
        reasons.append("Incoming dataset failed schema validation (missing columns or incompatible dtypes).")
        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.INSUFFICIENT_DATA,
            reasons=reasons,
            drift_detected=False,
            performance_status=perf_status,
            performance_degradation_confirmed=False,
            performance_metrics=performance_metrics,
            summary_note="Dataset schema is incompatible with reference schema, preventing reliable monitoring.",
        )

    if incoming_sample_count < min_samples_drift and labels_insufficient_or_absent:
        reasons.append(
            f"Incoming sample count ({incoming_sample_count}) is below minimum requirement ({min_samples_drift}) and labels are absent or insufficient."
        )
        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.INSUFFICIENT_DATA,
            reasons=reasons,
            drift_detected=False,
            performance_status=perf_status,
            performance_degradation_confirmed=False,
            performance_metrics=performance_metrics,
            summary_note="Insufficient data volume to evaluate distribution drift or model performance.",
        )

    overall_drift = drift_summary.overall_drift_detected if drift_summary else False
    perf_degradation_confirmed = False

    if performance_metrics and performance_metrics.status == "evaluated":
        perf_degradation_confirmed = performance_metrics.degradation_flagged

    # 3. DRIFT_AND_PERFORMANCE_DEGRADATION
    if overall_drift and perf_degradation_confirmed:
        reasons.append(
            f"Statistically significant data drift detected across {drift_summary.features_drifted} feature(s)."
        )
        reasons.append(
            f"Performance degradation confirmed on labelled batch (Accuracy/F1 drop exceeded tolerance)."
        )
        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.DRIFT_AND_PERFORMANCE_DEGRADATION,
            reasons=reasons,
            drift_detected=True,
            performance_status=perf_status,
            performance_degradation_confirmed=True,
            performance_metrics=performance_metrics,
            summary_note="Critical alert: Model performance degradation confirmed alongside significant feature distribution drift.",
        )

    # 4. PERFORMANCE_DEGRADATION
    if (not overall_drift) and perf_degradation_confirmed:
        reasons.append("Model accuracy/F1 dropped beyond tolerance on labelled incoming data.")
        reasons.append("No overall input data drift detected across monitored features.")
        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.PERFORMANCE_DEGRADATION,
            reasons=reasons,
            drift_detected=False,
            performance_status=perf_status,
            performance_degradation_confirmed=True,
            performance_metrics=performance_metrics,
            summary_note="Performance degradation confirmed without detectable input feature drift (possible concept drift).",
        )

    # 5. DRIFT_DETECTED
    if overall_drift:
        reasons.append(
            f"Input feature distribution drift detected (drift ratio: {drift_summary.drift_ratio*100:.1f}%)."
        )
        if perf_status == "labels_unavailable":
            reasons.append(
                "Ground-truth labels are unavailable for the incoming batch; performance loss is UNCONFIRMED."
            )
            note = "Data drift detected. Note: Performance impact is unconfirmed due to lack of ground-truth labels."
        else:
            reasons.append("Model performance remains within configured tolerance.")
            note = "Data drift detected, but model performance remains stable within acceptable tolerance."

        return ReliabilityAnalysisResponse(
            reliability_state=ReliabilityStateEnum.DRIFT_DETECTED,
            reasons=reasons,
            drift_detected=True,
            performance_status=perf_status,
            performance_degradation_confirmed=False,
            performance_metrics=performance_metrics,
            summary_note=note,
        )

    # 6. NORMAL
    reasons.append("No statistically significant data drift detected across monitored features.")
    if perf_status == "labels_unavailable":
        reasons.append("Labels unavailable: 'Normal' state reflects drift-only evidence.")
        note = "System normal based on input data drift analysis (ground-truth labels were unavailable)."
    elif perf_status == "evaluated":
        reasons.append("Model performance metrics match or exceed baseline expectations.")
        note = "System normal: No drift detected and model performance metrics are healthy."
    else:
        note = "System normal: No drift detected."

    return ReliabilityAnalysisResponse(
        reliability_state=ReliabilityStateEnum.NORMAL,
        reasons=reasons,
        drift_detected=False,
        performance_status=perf_status,
        performance_degradation_confirmed=False,
        performance_metrics=performance_metrics,
        summary_note=note,
    )
