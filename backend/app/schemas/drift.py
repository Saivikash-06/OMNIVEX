from typing import List, Optional
from pydantic import Field
from backend.app.schemas.common import (
    DriftStatusEnum,
    DriftTestNameEnum,
    MultipleTestingMethodEnum,
    StrictBaseModel,
)


class DriftFeatureResult(StrictBaseModel):
    feature: str
    feature_type: str  # numeric or categorical
    test_name: str
    statistic: float
    p_value: Optional[float] = None
    adjusted_p_value: Optional[float] = None
    threshold: float
    status: DriftStatusEnum
    reference_n: int
    incoming_n: int
    note: str


class DriftSummary(StrictBaseModel):
    features_tested: int
    features_skipped: int
    features_drifted: int
    drift_ratio: float
    overall_drift_detected: bool
    multiple_testing_method: MultipleTestingMethodEnum
    methodology_note: str = "Drift indicates distribution change, not confirmed performance loss."


class DriftAnalysisRequest(StrictBaseModel):
    reference_dataset_id: str
    incoming_dataset_id: str
    features_to_include: Optional[List[str]] = None
    features_to_exclude: Optional[List[str]] = None
    ks_alpha: float = Field(0.05, gt=0.0, lt=1.0)
    ks_min_effect: float = Field(0.10, ge=0.0)
    psi_moderate: float = Field(0.10, gt=0.0)
    psi_major: float = Field(0.25, gt=0.0)
    min_samples: int = Field(30, ge=5)
    multiple_testing_method: MultipleTestingMethodEnum = MultipleTestingMethodEnum.BENJAMINI_HOCHBERG
    drift_ratio_threshold: float = Field(0.30, ge=0.0, le=1.0)
    use_chi_square_for_categorical: bool = True


class DriftAnalysisResponse(StrictBaseModel):
    reference_dataset_id: str
    incoming_dataset_id: str
    per_feature_results: List[DriftFeatureResult]
    summary: DriftSummary
