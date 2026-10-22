from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_api_key
from backend.app.core.errors import NotFoundError
from backend.app.database.models import TrainedModel
from backend.app.schemas.common import AlgorithmEnum, PaginatedResponse
from backend.app.schemas.model import (
    BaselineMetrics,
    PredictRequest,
    PredictResponse,
    TrainModelRequest,
    TrainedModelResponse,
)
from backend.app.services.model_service import predict_dataset, train_model

router = APIRouter(prefix="/models", tags=["AI Models"])


def model_to_response(m: TrainedModel) -> TrainedModelResponse:
    return TrainedModelResponse(
        id=m.id,
        name=m.name,
        algorithm=AlgorithmEnum(m.algorithm),
        hyperparameters=m.hyperparameters,
        feature_names=m.feature_names,
        feature_dtypes=m.feature_dtypes,
        target_column=m.target_column,
        class_labels=m.class_labels,
        training_dataset_id=m.training_dataset_id,
        training_dataset_hash=m.training_dataset_hash,
        random_seed=m.random_seed,
        library_versions=m.library_versions,
        baseline_metrics=BaselineMetrics.model_validate(m.baseline_metrics),
        artifact_filename=m.artifact_filename,
        artifact_sha256=m.artifact_sha256,
        created_at=m.created_at,
    )


@router.post(
    "/train",
    response_model=TrainedModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Train Baseline Classification Model",
    description="Train a classification model from an uploaded reference dataset. Preprocessor and estimator are combined into an end-to-end pipeline.",
    dependencies=[Depends(require_api_key)],
)
def train_model_endpoint(
    request: TrainModelRequest,
    db: Session = Depends(get_db),
) -> TrainedModelResponse:
    model_record = train_model(db, request)
    return model_to_response(model_record)


@router.get(
    "",
    response_model=PaginatedResponse[TrainedModelResponse],
    summary="List Trained Models",
    description="List all registered trained models with metadata and baseline metrics.",
    dependencies=[Depends(require_api_key)],
)
def list_models(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TrainedModelResponse]:
    query = db.query(TrainedModel)
    total = query.count()
    records = query.order_by(TrainedModel.created_at.desc()).offset(offset).limit(limit).all()
    items = [model_to_response(m) for m in records]

    return PaginatedResponse[TrainedModelResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{model_id}",
    response_model=TrainedModelResponse,
    summary="Get Model Details",
    description="Retrieve details and baseline metrics for a specific trained model.",
    dependencies=[Depends(require_api_key)],
)
def get_model(
    model_id: str,
    db: Session = Depends(get_db),
) -> TrainedModelResponse:
    model_record = db.query(TrainedModel).filter(TrainedModel.id == model_id).first()
    if not model_record:
        raise NotFoundError("Model", model_id)
    return model_to_response(model_record)


@router.post(
    "/{model_id}/predict",
    response_model=PredictResponse,
    summary="Predict on Dataset",
    description="Perform inference with a stored model on a dataset after validating feature compatibility.",
    dependencies=[Depends(require_api_key)],
)
def predict_endpoint(
    model_id: str,
    request: PredictRequest,
    db: Session = Depends(get_db),
) -> PredictResponse:
    return predict_dataset(db, model_id, request.dataset_id)
