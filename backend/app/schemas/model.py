import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field
from backend.app.schemas.common import AlgorithmEnum, StrictBaseModel


class TrainModelRequest(StrictBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    dataset_id: str
    target_column: str
    feature_columns: Optional[List[str]] = None
    algorithm: AlgorithmEnum = AlgorithmEnum.LOGISTIC_REGRESSION
    hyperparameters: Optional[Dict[str, Any]] = None
    test_size: float = Field(0.2, ge=0.1, le=0.5)
    random_seed: int = Field(42, ge=0)


class BaselineMetrics(StrictBaseModel):
    accuracy: float
    precision: float
    recall: float
    f1: float
    f1_average: str = "macro"
    confusion_matrix: List[List[int]]
    sample_size: int


class TrainedModelResponse(StrictBaseModel):
    id: str
    name: str
    algorithm: AlgorithmEnum
    hyperparameters: Dict[str, Any]
    feature_names: List[str]
    feature_dtypes: Dict[str, str]
    target_column: str
    class_labels: List[str]
    training_dataset_id: str
    training_dataset_hash: str
    random_seed: int
    library_versions: Dict[str, str]
    baseline_metrics: BaselineMetrics
    artifact_filename: str
    artifact_sha256: str
    created_at: datetime.datetime


class PredictRequest(StrictBaseModel):
    dataset_id: str


class PredictResponse(StrictBaseModel):
    model_id: str
    dataset_id: str
    sample_count: int
    predictions: List[str]
    probabilities: Optional[List[List[float]]] = None
    feature_names: List[str]
