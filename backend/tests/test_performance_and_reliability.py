import pytest
import numpy as np
from backend.app.schemas.common import MetricAverageEnum, MultipleTestingMethodEnum, ReliabilityStateEnum
from backend.app.schemas.drift import DriftSummary
from backend.app.schemas.performance import (
    PerformanceAnalysisRequest,
    PerformanceMetricsDetail,
)
from backend.app.services.performance_service import compute_performance_metrics
from backend.app.services.reliability_service import evaluate_reliability_state


def test_hand_computed_performance_metrics():
    """Verify performance metrics against hand-calculated values on known predictions."""
    # 40 samples, 2 classes: 0 and 1
    # 20 True 1s: 18 predicted 1, 2 predicted 0
    # 20 True 0s: 16 predicted 0, 4 predicted 1
    # Total correct: 18 + 16 = 34 / 40 = 0.85 Accuracy
    # Class 1: TP=18, FP=4 -> Prec1 = 18/22 = 0.8182, Rec1 = 18/20 = 0.9000, F1_1 = 2*(0.8182*0.9)/(1.7182) = 0.8571
    # Class 0: TP=16, FP=2 -> Prec0 = 16/18 = 0.8889, Rec0 = 16/20 = 0.8000, F1_0 = 2*(0.8889*0.8)/(1.6889) = 0.8421
    # Macro F1 = (0.8571 + 0.8421) / 2 = 0.8496
    y_true = np.array(["1"] * 20 + ["0"] * 20)
    y_pred = np.array(["1"] * 18 + ["0"] * 2 + ["1"] * 4 + ["0"] * 16)

    baseline = {"accuracy": 0.85, "f1": 0.85}
    req = PerformanceAnalysisRequest(
        model_id="m1",
        dataset_id="d1",
        min_samples=30,
        f1_average=MetricAverageEnum.MACRO,
        bootstrap_resamples=200,
        random_seed=42,
    )
    res = compute_performance_metrics(
        y_true=y_true,
        y_pred=y_pred,
        training_classes=["0", "1"],
        baseline_metrics=baseline,
        request=req,
    )
    assert res.accuracy == 0.85
    assert abs(res.f1 - 0.8496) < 0.005
    assert res.sample_size == 40
    assert res.status == "evaluated"
    assert res.accuracy_ci is not None
    assert res.accuracy_ci.lower <= 0.85 <= res.accuracy_ci.upper


def test_insufficient_labelled_samples():
    y_true = np.array(["1"] * 10 + ["0"] * 10)
    y_pred = np.array(["1"] * 10 + ["0"] * 10)

    req = PerformanceAnalysisRequest(
        model_id="m1",
        dataset_id="d1",
        min_samples=30,
    )
    res = compute_performance_metrics(
        y_true=y_true,
        y_pred=y_pred,
        training_classes=["0", "1"],
        baseline_metrics={"accuracy": 1.0, "f1": 1.0},
        request=req,
    )
    assert res.status == "insufficient_data"
    assert res.accuracy is None
    assert res.f1 is None
    assert res.sample_size == 20


def test_reliability_state_1_monitoring_error():
    res = evaluate_reliability_state(
        drift_summary=None,
        performance_metrics=None,
        computation_error="ZeroDivisionError in custom metric",
    )
    assert res.reliability_state == ReliabilityStateEnum.MONITORING_ERROR
    assert "ZeroDivisionError" in res.reasons[0]


def test_reliability_state_2_insufficient_data():
    # Schema invalid
    res_schema = evaluate_reliability_state(
        drift_summary=None,
        performance_metrics=None,
        schema_valid=False,
    )
    assert res_schema.reliability_state == ReliabilityStateEnum.INSUFFICIENT_DATA

    # Sample size < 30 and labels unavailable
    perf_unavail = PerformanceMetricsDetail(
        sample_size=10,
        status="labels_unavailable",
    )
    res_small = evaluate_reliability_state(
        drift_summary=None,
        performance_metrics=perf_unavail,
        incoming_sample_count=10,
        min_samples_drift=30,
    )
    assert res_small.reliability_state == ReliabilityStateEnum.INSUFFICIENT_DATA


def test_reliability_state_3_drift_and_performance_degradation():
    drift = DriftSummary(
        features_tested=5,
        features_skipped=0,
        features_drifted=3,
        drift_ratio=0.6,
        overall_drift_detected=True,
        multiple_testing_method=MultipleTestingMethodEnum.BENJAMINI_HOCHBERG,
    )
    perf = PerformanceMetricsDetail(
        accuracy=0.60,
        f1=0.55,
        sample_size=100,
        degradation_flagged=True,
        status="evaluated",
    )
    res = evaluate_reliability_state(
        drift_summary=drift,
        performance_metrics=perf,
        incoming_sample_count=100,
    )
    assert res.reliability_state == ReliabilityStateEnum.DRIFT_AND_PERFORMANCE_DEGRADATION
    assert res.drift_detected is True
    assert res.performance_degradation_confirmed is True


def test_reliability_state_4_performance_degradation_without_drift():
    drift = DriftSummary(
        features_tested=5,
        features_skipped=0,
        features_drifted=0,
        drift_ratio=0.0,
        overall_drift_detected=False,
        multiple_testing_method=MultipleTestingMethodEnum.BENJAMINI_HOCHBERG,
    )
    perf = PerformanceMetricsDetail(
        accuracy=0.60,
        f1=0.55,
        sample_size=100,
        degradation_flagged=True,
        status="evaluated",
    )
    res = evaluate_reliability_state(
        drift_summary=drift,
        performance_metrics=perf,
        incoming_sample_count=100,
    )
    assert res.reliability_state == ReliabilityStateEnum.PERFORMANCE_DEGRADATION
    assert res.drift_detected is False
    assert res.performance_degradation_confirmed is True


def test_reliability_state_5_drift_detected_labels_unavailable():
    drift = DriftSummary(
        features_tested=5,
        features_skipped=0,
        features_drifted=3,
        drift_ratio=0.6,
        overall_drift_detected=True,
        multiple_testing_method=MultipleTestingMethodEnum.BENJAMINI_HOCHBERG,
    )
    perf = PerformanceMetricsDetail(
        sample_size=100,
        status="labels_unavailable",
    )
    res = evaluate_reliability_state(
        drift_summary=drift,
        performance_metrics=perf,
        incoming_sample_count=100,
    )
    assert res.reliability_state == ReliabilityStateEnum.DRIFT_DETECTED
    assert res.drift_detected is True
    assert res.performance_degradation_confirmed is False
    assert res.performance_status == "labels_unavailable"
    assert "unconfirmed" in res.summary_note.lower()


def test_reliability_state_6_normal():
    drift = DriftSummary(
        features_tested=5,
        features_skipped=0,
        features_drifted=0,
        drift_ratio=0.0,
        overall_drift_detected=False,
        multiple_testing_method=MultipleTestingMethodEnum.BENJAMINI_HOCHBERG,
    )
    perf = PerformanceMetricsDetail(
        accuracy=0.92,
        f1=0.91,
        sample_size=100,
        degradation_flagged=False,
        status="evaluated",
    )
    res = evaluate_reliability_state(
        drift_summary=drift,
        performance_metrics=perf,
        incoming_sample_count=100,
    )
    assert res.reliability_state == ReliabilityStateEnum.NORMAL
    assert res.drift_detected is False
    assert res.performance_degradation_confirmed is False
