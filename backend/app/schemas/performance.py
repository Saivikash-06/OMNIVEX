from typing import Any, Dict, List, Optional
from pydantic import Field
from backend.app.schemas.common import MetricAverageEnum, ReliabilityStateEnum, StrictBaseModel


class ConfidenceInterval(StrictBaseModel):
    lower: float
    upper: float
    confidence_level: float = 0.95


class PerformanceMetricsDetail(StrictBaseModel):
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    f1_average: MetricAverageEnum = MetricAverageEnum.MACRO
    confusion_matrix: Optional[List[List[int]]] = None
    class_labels: Optional[List[str]] = None
    abs_diff_accuracy: Optional[float] = None
    rel_diff_accuracy: Optional[float] = None
    abs_diff_f1: Optional[float] = None
    rel_diff_f1: Optional[float] = None
    accuracy_ci: Optional[ConfidenceInterval] = None
    f1_ci: Optional[ConfidenceInterval] = None
    sample_size: int
    degradation_flagged: bool = False
    status: str  # evaluated, insufficient_data, labels_unavailable
    absent_classes: List[str] = Field(default_factory=list)
    unseen_classes: List[str] = Field(default_factory=list)
    note: str = ""


class PerformanceAnalysisRequest(StrictBaseModel):
    model_id: str
    dataset_id: str
    label_column: Optional[str] = None
    f1_average: MetricAverageEnum = MetricAverageEnum.MACRO
    pos_label: Optional[str] = None
    min_samples: int = Field(30, ge=5)
    performance_drop_tolerance: float = Field(0.05, ge=0.0, le=1.0)
    bootstrap_resamples: int = Field(1000, ge=100, le=2000)
    random_seed: int = Field(42, ge=0)


class ReliabilityAnalysisResponse(StrictBaseModel):
    reliability_state: ReliabilityStateEnum
    reasons: List[str]
    drift_detected: bool
    performance_status: str
    performance_degradation_confirmed: bool
    performance_metrics: Optional[PerformanceMetricsDetail] = None
    summary_note: str
