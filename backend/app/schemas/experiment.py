import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field
from backend.app.schemas.alert import AlertResponse
from backend.app.schemas.common import MultipleTestingMethodEnum, SimulationTypeEnum, StrictBaseModel
from backend.app.schemas.drift import DriftAnalysisResponse
from backend.app.schemas.performance import PerformanceMetricsDetail, ReliabilityAnalysisResponse


class SimulationParameters(StrictBaseModel):
    simulation_type: SimulationTypeEnum = SimulationTypeEnum.NONE
    magnitude: float = Field(1.0, ge=0.0, le=10.0)
    target_features: Optional[List[str]] = None
    seed: int = Field(42, ge=0)


class CreateExperimentRequest(StrictBaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    scenario: str = Field("baseline", min_length=1, max_length=50)
    reference_dataset_id: str
    incoming_dataset_id: str
    model_id: Optional[str] = None
    label_column: Optional[str] = None
    simulation: Optional[SimulationParameters] = None
    ks_alpha: float = Field(0.05, gt=0.0, lt=1.0)
    ks_min_effect: float = Field(0.10, ge=0.0)
    psi_moderate: float = Field(0.10, gt=0.0)
    psi_major: float = Field(0.25, gt=0.0)
    min_samples: int = Field(30, ge=5)
    multiple_testing_method: MultipleTestingMethodEnum = MultipleTestingMethodEnum.BENJAMINI_HOCHBERG
    drift_ratio_threshold: float = Field(0.30, ge=0.0, le=1.0)
    performance_drop_tolerance: float = Field(0.05, ge=0.0, le=1.0)
    random_seed: int = Field(42, ge=0)


class ExperimentResultResponse(StrictBaseModel):
    experiment_id: str
    run_id: str
    name: str
    scenario: str
    is_simulation: bool
    simulation_parameters: Optional[SimulationParameters] = None
    status: str
    reference_dataset_id: str
    incoming_dataset_id: str
    model_id: Optional[str] = None
    reliability: ReliabilityAnalysisResponse
    drift_results: Optional[DriftAnalysisResponse] = None
    performance_metrics: Optional[PerformanceMetricsDetail] = None
    alerts: List[AlertResponse] = Field(default_factory=list)
    execution_time_ms: float
    random_seed: int
    library_versions: Dict[str, str]
    created_at: datetime.datetime
