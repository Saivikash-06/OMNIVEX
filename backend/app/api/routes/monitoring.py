from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_api_key
from backend.app.database.models import DatasetModel, MonitoringRunModel
from backend.app.schemas.drift import DriftAnalysisRequest, DriftAnalysisResponse
from backend.app.schemas.experiment import CreateExperimentRequest, ExperimentResultResponse
from backend.app.schemas.performance import PerformanceAnalysisRequest, PerformanceMetricsDetail
from backend.app.services.dataset_service import get_dataset_by_id, load_dataset_dataframe
from backend.app.services.drift_service import compute_drift_analysis

router = APIRouter(prefix="/monitor", tags=["Monitoring"])


@router.post(
    "/drift",
    response_model=DriftAnalysisResponse,
    summary="Analyze Data Drift",
    description="Compute Kolmogorov-Smirnov (KS), PSI, and Chi-Square tests with multiple testing correction.",
    dependencies=[Depends(require_api_key)],
)
def analyze_drift(
    request: DriftAnalysisRequest,
    db: Session = Depends(get_db),
) -> DriftAnalysisResponse:
    ref_dataset = get_dataset_by_id(db, request.reference_dataset_id)
    inc_dataset = get_dataset_by_id(db, request.incoming_dataset_id)

    ref_df = load_dataset_dataframe(ref_dataset)
    inc_df = load_dataset_dataframe(inc_dataset)

    return compute_drift_analysis(ref_df, inc_df, request)


@router.post(
    "/performance",
    response_model=PerformanceMetricsDetail,
    summary="Evaluate Model Performance",
    description="Compute accuracy, F1, precision, recall, confusion matrix, and bootstrap confidence intervals against baseline.",
    dependencies=[Depends(require_api_key)],
)
def analyze_performance(
    request: PerformanceAnalysisRequest,
    db: Session = Depends(get_db),
) -> PerformanceMetricsDetail:
    from backend.app.services.performance_service import evaluate_dataset_performance
    return evaluate_dataset_performance(db, request)


@router.post(
    "/run",
    response_model=ExperimentResultResponse,
    summary="Full Monitoring Run",
    description="Execute full monitoring cycle: validation -> drift -> prediction/performance -> reliability -> alerts -> persistence.",
    dependencies=[Depends(require_api_key)],
)
def run_monitoring_cycle(
    request: CreateExperimentRequest,
    db: Session = Depends(get_db),
) -> ExperimentResultResponse:
    from backend.app.services.experiment_service import run_experiment
    return run_experiment(db, request)


@router.get(
    "/summary",
    summary="Latest Monitoring Summary",
    description="Retrieve the latest monitoring run summary, reliability state, and drift status.",
    dependencies=[Depends(require_api_key)],
)
def get_latest_summary(
    db: Session = Depends(get_db),
):
    run = db.query(MonitoringRunModel).order_by(MonitoringRunModel.created_at.desc()).first()
    if not run:
        from backend.app.core.errors import NotFoundError
        raise NotFoundError("Monitoring Run", "latest")

    return {
        "run_id": run.id,
        "experiment_id": run.experiment_id,
        "reliability_state": run.reliability_state,
        "drift_detected": run.drift_detected,
        "performance_status": run.performance_status,
        "reasons": run.reasons,
        "execution_time_ms": run.execution_time_ms,
        "created_at": run.created_at,
    }
