from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_api_key
from backend.app.core.errors import NotFoundError, ValidationAppError
from backend.app.database.models import ExperimentModel, MonitoringRunModel
from backend.app.schemas.common import PaginatedResponse
from backend.app.schemas.experiment import CreateExperimentRequest, ExperimentResultResponse
from backend.app.services.experiment_service import (
    export_experiment_csv,
    export_experiment_json,
    run_experiment,
)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


@router.post(
    "",
    response_model=ExperimentResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and Run Experiment",
    description="Run an end-to-end monitoring experiment with optional drift simulation.",
    dependencies=[Depends(require_api_key)],
)
def create_experiment_endpoint(
    request: CreateExperimentRequest,
    db: Session = Depends(get_db),
) -> ExperimentResultResponse:
    return run_experiment(db, request)


@router.get(
    "",
    summary="List Experiments",
    description="List all historical monitoring experiments with pagination.",
    dependencies=[Depends(require_api_key)],
)
def list_experiments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ExperimentModel)
    total = query.count()
    records = query.order_by(ExperimentModel.created_at.desc()).offset(offset).limit(limit).all()

    items = [
        {
            "id": r.id,
            "name": r.name,
            "scenario": r.scenario,
            "is_simulation": r.is_simulation,
            "status": r.status,
            "reference_dataset_id": r.reference_dataset_id,
            "incoming_dataset_id": r.incoming_dataset_id,
            "model_id": r.model_id,
            "created_at": r.created_at,
        }
        for r in records
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{experiment_id}",
    summary="Get Experiment Details",
    description="Retrieve full details, run parameters, and settings for an experiment.",
    dependencies=[Depends(require_api_key)],
)
def get_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
):
    experiment = db.query(ExperimentModel).filter(ExperimentModel.id == experiment_id).first()
    if not experiment:
        raise NotFoundError("Experiment", experiment_id)

    run = db.query(MonitoringRunModel).filter(MonitoringRunModel.experiment_id == experiment_id).first()

    return {
        "experiment": {
            "id": experiment.id,
            "name": experiment.name,
            "scenario": experiment.scenario,
            "is_simulation": experiment.is_simulation,
            "simulation_parameters": experiment.simulation_parameters,
            "status": experiment.status,
            "created_at": experiment.created_at,
            "random_seed": experiment.random_seed,
            "library_versions": experiment.library_versions,
        },
        "run": {
            "id": run.id if run else None,
            "reliability_state": run.reliability_state if run else None,
            "drift_detected": run.drift_detected if run else None,
            "performance_status": run.performance_status if run else None,
            "reasons": run.reasons if run else [],
        }
    }


@router.get(
    "/{experiment_id}/export",
    summary="Export Experiment Results",
    description="Download experiment findings as sanitized CSV or JSON.",
    dependencies=[Depends(require_api_key)],
)
def export_experiment(
    experiment_id: str,
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format: csv or json"),
    db: Session = Depends(get_db),
):
    experiment = db.query(ExperimentModel).filter(ExperimentModel.id == experiment_id).first()
    if not experiment:
        raise NotFoundError("Experiment", experiment_id)

    run = db.query(MonitoringRunModel).filter(MonitoringRunModel.experiment_id == experiment_id).first()
    if not run:
        raise NotFoundError("Monitoring Run for Experiment", experiment_id)

    if format == "csv":
        csv_text = export_experiment_csv(experiment, run)
        filename = f"experiment_{experiment_id[:8]}_{'simulated' if experiment.is_simulation else 'observed'}.csv"
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        json_data = export_experiment_json(experiment, run)
        return JSONResponse(content=json_data)
