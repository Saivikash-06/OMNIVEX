from enum import Enum
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetRole(str, Enum):
    REFERENCE = "reference"
    INCOMING = "incoming"


class AlgorithmEnum(str, Enum):
    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    DECISION_TREE = "decision_tree"


class MetricAverageEnum(str, Enum):
    MACRO = "macro"
    WEIGHTED = "weighted"
    BINARY = "binary"


class DriftTestNameEnum(str, Enum):
    KS = "kolmogorov_smirnov"
    PSI = "psi"
    CHI_SQUARE = "chi_square"


class DriftStatusEnum(str, Enum):
    DRIFT = "drift"
    NO_DRIFT = "no_drift"
    SIGNIFICANT_LOW_EFFECT = "significant_low_effect"
    SKIPPED_INSUFFICIENT_DATA = "skipped_insufficient_data"
    SKIPPED_CONSTANT_FEATURE = "skipped_constant_feature"
    ERROR = "error"


class MultipleTestingMethodEnum(str, Enum):
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    BONFERRONI = "bonferroni"
    NONE = "none"


class ReliabilityStateEnum(str, Enum):
    MONITORING_ERROR = "MONITORING_ERROR"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DRIFT_AND_PERFORMANCE_DEGRADATION = "DRIFT_AND_PERFORMANCE_DEGRADATION"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    NORMAL = "NORMAL"


class AlertSeverityEnum(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SimulationTypeEnum(str, Enum):
    NONE = "none"
    MEAN_SHIFT = "mean_shift"
    VARIANCE_SCALE = "variance_scale"
    CATEGORICAL_SHIFT = "categorical_shift"
    MISSING_VALUES = "missing_values"
    GRADUAL_DRIFT = "gradual_drift"


class ErrorDetail(StrictBaseModel):
    code: str
    message: str
    details: List[str] = Field(default_factory=list)


class ErrorResponse(StrictBaseModel):
    error: ErrorDetail


class PaginatedResponse(StrictBaseModel, Generic[T]):
    items: List[T]
    total: int = Field(..., ge=0)
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
