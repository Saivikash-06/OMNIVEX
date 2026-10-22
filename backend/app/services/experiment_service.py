import csv
import datetime
import io
import json
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import NotFoundError, ValidationAppError
from backend.app.core.security import sanitize_formula_injection
from backend.app.database.models import (
    AlertModel,
    DriftResultModel,
    ExperimentModel,
    MonitoringRunModel,
    PerformanceMetricModel,
    TrainedModel,
)
from backend.app.schemas.alert import AlertResponse
from backend.app.schemas.common import AlertSeverityEnum, SimulationTypeEnum
from backend.app.schemas.dataset import DatasetSchemaInfo
from backend.app.schemas.drift import DriftAnalysisRequest, DriftAnalysisResponse, DriftFeatureResult, DriftSummary
from backend.app.schemas.experiment import (
    CreateExperimentRequest,
    ExperimentResultResponse,
    SimulationParameters,
)
from backend.app.schemas.performance import (
    PerformanceAnalysisRequest,
    PerformanceMetricsDetail,
    ReliabilityAnalysisResponse,
)
from backend.app.services.alert_service import generate_alerts_from_monitoring
from backend.app.services.dataset_service import (
    get_dataset_by_id,
    load_dataset_dataframe,
    validate_incoming_against_reference,
)
from backend.app.services.drift_service import compute_drift_analysis
from backend.app.services.model_service import get_library_versions, load_model_pipeline
from backend.app.services.performance_service import compute_performance_metrics
from backend.app.services.reliability_service import evaluate_reliability_state
from backend.app.services.simulation import apply_drift_simulation


def run_experiment(
    db: Session,
    request: CreateExperimentRequest,
) -> ExperimentResultResponse:
    """Execute end-to-end monitoring experiment: validation, drift, performance,

    reliability, alerts, and persistence.
    """
    start_time = time.perf_counter()

    ref_dataset = get_dataset_by_id(db, request.reference_dataset_id)
    inc_dataset = get_dataset_by_id(db, request.incoming_dataset_id)

    ref_df = load_dataset_dataframe(ref_dataset)
    inc_df = load_dataset_dataframe(inc_dataset)

    # Check simulation
    is_simulation = False
    sim_params = request.simulation
    if sim_params and sim_params.simulation_type != SimulationTypeEnum.NONE:
        is_simulation = True
        inc_df = apply_drift_simulation(inc_df, sim_params)

    # 1. Schema validation
    ref_schema = DatasetSchemaInfo.model_validate(ref_dataset.schema_json)
    is_valid, schema_issues, quality_summary = validate_incoming_against_reference(
        ref_schema=ref_schema,
        incoming_df=inc_df,
        target_column=request.label_column,
    )

    # 2. Drift analysis
    drift_req = DriftAnalysisRequest(
        reference_dataset_id=ref_dataset.id,
        incoming_dataset_id=inc_dataset.id,
        ks_alpha=request.ks_alpha,
        ks_min_effect=request.ks_min_effect,
        psi_moderate=request.psi_moderate,
        psi_major=request.psi_major,
        min_samples=request.min_samples,
        multiple_testing_method=request.multiple_testing_method,
        drift_ratio_threshold=request.drift_ratio_threshold,
    )
    drift_response = compute_drift_analysis(ref_df, inc_df, drift_req)

    # 3. Model performance evaluation (if model_id provided)
    perf_metrics: Optional[PerformanceMetricsDetail] = None
    if request.model_id:
        model_record = db.query(TrainedModel).filter(TrainedModel.id == request.model_id).first()
        if not model_record:
            raise NotFoundError("Model", request.model_id)

        target_col = request.label_column or model_record.target_column
        if target_col in inc_df.columns and not inc_df[target_col].isnull().all():
            req_features = model_record.feature_names
            # Check features exist in incoming
            missing_feats = [f for f in req_features if f not in inc_df.columns]
            if not missing_feats:
                pipeline = load_model_pipeline(model_record)
                valid_mask = inc_df[target_col].notnull()
                eval_df = inc_df[valid_mask]
                if len(eval_df) > 0:
                    y_true = eval_df[target_col].values
                    y_pred = pipeline.predict(eval_df[req_features])
                    perf_metrics = compute_performance_metrics(
                        y_true=y_true,
                        y_pred=y_pred,
                        training_classes=model_record.class_labels,
                        baseline_metrics=model_record.baseline_metrics,
                        request=PerformanceAnalysisRequest(
                            model_id=request.model_id,
                            dataset_id=request.incoming_dataset_id,
                            label_column=target_col,
                            min_samples=request.min_samples,
                            performance_drop_tolerance=request.performance_drop_tolerance,
                            random_seed=request.random_seed,
                        ),
                    )
        else:
            perf_metrics = PerformanceMetricsDetail(
                sample_size=len(inc_df),
                status="labels_unavailable",
                note="Labels are unavailable in incoming dataset; performance impact is unconfirmed.",
            )

    # 4. Reliability analysis
    reliability_resp = evaluate_reliability_state(
        drift_summary=drift_response.summary,
        performance_metrics=perf_metrics,
        schema_valid=is_valid,
        incoming_sample_count=len(inc_df),
        min_samples_drift=request.min_samples,
    )

    execution_time_ms = (time.perf_counter() - start_time) * 1000.0

    # 5. Persist records
    experiment_record = ExperimentModel(
        name=request.name,
        description=request.description,
        scenario=request.scenario,
        is_simulation=is_simulation,
        simulation_parameters=sim_params.model_dump() if sim_params else None,
        reference_dataset_id=ref_dataset.id,
        incoming_dataset_id=inc_dataset.id,
        model_id=request.model_id,
        settings_snapshot=request.model_dump(),
        random_seed=request.random_seed,
        library_versions=get_library_versions(),
        status="completed",
    )
    db.add(experiment_record)
    db.flush()

    run_record = MonitoringRunModel(
        experiment_id=experiment_record.id,
        reference_dataset_id=ref_dataset.id,
        incoming_dataset_id=inc_dataset.id,
        model_id=request.model_id,
        reliability_state=reliability_resp.reliability_state.value,
        reasons=reliability_resp.reasons,
        drift_detected=reliability_resp.drift_detected,
        performance_status=reliability_resp.performance_status,
        execution_time_ms=round(execution_time_ms, 2),
        settings_snapshot=request.model_dump(),
    )
    db.add(run_record)
    db.flush()

    # Store drift results
    for feat in drift_response.per_feature_results:
        db.add(
            DriftResultModel(
                run_id=run_record.id,
                feature=feat.feature,
                feature_type=feat.feature_type,
                test_name=feat.test_name,
                statistic=feat.statistic,
                p_value=feat.p_value,
                adjusted_p_value=feat.adjusted_p_value,
                threshold=feat.threshold,
                status=feat.status.value,
                reference_n=feat.reference_n,
                incoming_n=feat.incoming_n,
                note=feat.note,
            )
        )

    # Store performance metrics
    if perf_metrics and perf_metrics.status == "evaluated":
        db.add(
            PerformanceMetricModel(
                run_id=run_record.id,
                accuracy=perf_metrics.accuracy,
                precision=perf_metrics.precision,
                recall=perf_metrics.recall,
                f1=perf_metrics.f1,
                f1_average=perf_metrics.f1_average.value,
                confusion_matrix=perf_metrics.confusion_matrix,
                class_labels=perf_metrics.class_labels,
                accuracy_ci=perf_metrics.accuracy_ci.model_dump() if perf_metrics.accuracy_ci else None,
                f1_ci=perf_metrics.f1_ci.model_dump() if perf_metrics.f1_ci else None,
                sample_size=perf_metrics.sample_size,
                degradation_flagged=perf_metrics.degradation_flagged,
            )
        )

    # 6. Generate and persist alerts
    created_alert_models = generate_alerts_from_monitoring(
        db=db,
        run_id=run_record.id,
        schema_issues=schema_issues,
        drift_response=drift_response,
        perf_metrics=perf_metrics,
        reliability_response=reliability_resp,
    )

    db.commit()
    db.refresh(experiment_record)
    db.refresh(run_record)

    alert_responses = [
        AlertResponse(
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
        for a in created_alert_models
    ]

    return ExperimentResultResponse(
        experiment_id=experiment_record.id,
        run_id=run_record.id,
        name=experiment_record.name,
        scenario=experiment_record.scenario,
        is_simulation=is_simulation,
        simulation_parameters=sim_params,
        status="completed",
        reference_dataset_id=ref_dataset.id,
        incoming_dataset_id=inc_dataset.id,
        model_id=request.model_id,
        reliability=reliability_resp,
        drift_results=drift_response,
        performance_metrics=perf_metrics,
        alerts=alert_responses,
        execution_time_ms=round(execution_time_ms, 2),
        random_seed=request.random_seed,
        library_versions=experiment_record.library_versions,
        created_at=experiment_record.created_at,
    )


def export_experiment_csv(experiment: ExperimentModel, run: MonitoringRunModel) -> str:
    """Generate CSV report neutralizing spreadsheet formula injection."""
    output = io.StringIO()
    writer = csv.writer(output)

    sim_tag = "SIMULATED" if experiment.is_simulation else "REAL"

    # Header section
    writer.writerow(["OMNIVEX Monitoring Experiment Export", f"[{sim_tag}]"])
    writer.writerow(["Experiment ID", experiment.id])
    writer.writerow(["Experiment Name", sanitize_formula_injection(experiment.name)])
    writer.writerow(["Scenario", sanitize_formula_injection(experiment.scenario)])
    writer.writerow(["Is Simulation", str(experiment.is_simulation)])
    writer.writerow(["Reliability State", run.reliability_state])
    writer.writerow(["Drift Detected", str(run.drift_detected)])
    writer.writerow(["Performance Status", run.performance_status])
    writer.writerow(["Created At (UTC)", run.created_at.isoformat()])
    writer.writerow([])

    # Drift Table
    writer.writerow(["Feature Drift Results"])
    writer.writerow([
        "Feature",
        "Feature Type",
        "Test Name",
        "Statistic",
        "P-Value",
        "Adjusted P-Value",
        "Threshold",
        "Status",
        "Ref N",
        "Inc N",
        "Note",
    ])
    for d in run.drift_results:
        writer.writerow([
            sanitize_formula_injection(d.feature),
            d.feature_type,
            d.test_name,
            f"{d.statistic:.6f}",
            f"{d.p_value:.6f}" if d.p_value is not None else "N/A",
            f"{d.adjusted_p_value:.6f}" if d.adjusted_p_value is not None else "N/A",
            f"{d.threshold:.4f}",
            d.status,
            d.reference_n,
            d.incoming_n,
            sanitize_formula_injection(d.note or ""),
        ])
    writer.writerow([])

    # Performance Section
    if run.performance_metrics:
        p = run.performance_metrics
        writer.writerow(["Model Performance Metrics"])
        writer.writerow(["Accuracy", f"{p.accuracy:.4f}" if p.accuracy is not None else "N/A"])
        writer.writerow(["Precision", f"{p.precision:.4f}" if p.precision is not None else "N/A"])
        writer.writerow(["Recall", f"{p.recall:.4f}" if p.recall is not None else "N/A"])
        writer.writerow(["F1", f"{p.f1:.4f}" if p.f1 is not None else "N/A"])
        writer.writerow(["Sample Size", p.sample_size])
        writer.writerow(["Degradation Flagged", str(p.degradation_flagged)])
        writer.writerow([])

    # Alerts Section
    writer.writerow(["Alerts Generated"])
    writer.writerow(["Severity", "Alert Type", "Affected Target", "Explanation"])
    for a in run.alerts:
        writer.writerow([
            a.severity,
            a.alert_type,
            sanitize_formula_injection(a.affected_feature_or_metric),
            sanitize_formula_injection(a.explanation),
        ])

    return output.getvalue()


def export_experiment_json(experiment: ExperimentModel, run: MonitoringRunModel) -> Dict[str, Any]:
    """Generate structured JSON export with metadata and SIMULATED tag."""
    return {
        "schema_version": "2.0.0",
        "tag": "SIMULATED" if experiment.is_simulation else "OBSERVED",
        "experiment": {
            "id": experiment.id,
            "name": experiment.name,
            "scenario": experiment.scenario,
            "is_simulation": experiment.is_simulation,
            "simulation_parameters": experiment.simulation_parameters,
            "created_at": experiment.created_at.isoformat(),
            "library_versions": experiment.library_versions,
            "random_seed": experiment.random_seed,
        },
        "monitoring_run": {
            "id": run.id,
            "reliability_state": run.reliability_state,
            "reasons": run.reasons,
            "drift_detected": run.drift_detected,
            "performance_status": run.performance_status,
            "execution_time_ms": run.execution_time_ms,
        },
        "drift_results": [
            {
                "feature": d.feature,
                "feature_type": d.feature_type,
                "test_name": d.test_name,
                "statistic": d.statistic,
                "p_value": d.p_value,
                "adjusted_p_value": d.adjusted_p_value,
                "threshold": d.threshold,
                "status": d.status,
                "note": d.note,
            }
            for d in run.drift_results
        ],
        "performance_metrics": (
            {
                "accuracy": run.performance_metrics.accuracy,
                "precision": run.performance_metrics.precision,
                "recall": run.performance_metrics.recall,
                "f1": run.performance_metrics.f1,
                "confusion_matrix": run.performance_metrics.confusion_matrix,
                "degradation_flagged": run.performance_metrics.degradation_flagged,
            }
            if run.performance_metrics
            else None
        ),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "affected": a.affected_feature_or_metric,
                "explanation": a.explanation,
                "suggested_steps": a.suggested_steps,
            }
            for a in run.alerts
        ],
    }
