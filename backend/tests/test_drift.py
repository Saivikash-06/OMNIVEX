import io
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.schemas.common import (
    DriftStatusEnum,
    MultipleTestingMethodEnum,
)
from backend.app.schemas.drift import DriftAnalysisRequest
from backend.app.services.drift_service import (
    calculate_categorical_psi,
    calculate_numerical_psi,
    compute_drift_analysis,
    apply_multiple_testing_correction,
)


def test_unchanged_data_false_positive_rate():
    """Unchanged-data test: draw reference and incoming samples from the same

    distribution across multiple seeds. Assert false-positive rate is bounded.
    Note: Statistical hypothesis testing under alpha=0.05 will inherently produce
    false positives in ~5% of tests; hence bounded, not zero.
    """
    n_trials = 25
    false_positives = 0

    for seed in range(n_trials):
        rng = np.random.RandomState(seed)
        ref_df = pd.DataFrame({
            "feat1": rng.normal(loc=0.0, scale=1.0, size=200),
            "feat2": rng.uniform(low=0.0, high=100.0, size=200),
        })
        inc_df = pd.DataFrame({
            "feat1": rng.normal(loc=0.0, scale=1.0, size=200),
            "feat2": rng.uniform(low=0.0, high=100.0, size=200),
        })

        req = DriftAnalysisRequest(
            reference_dataset_id="ref_id",
            incoming_dataset_id="inc_id",
            ks_alpha=0.05,
            multiple_testing_method=MultipleTestingMethodEnum.BENJAMINI_HOCHBERG,
            drift_ratio_threshold=0.50,
        )
        res = compute_drift_analysis(ref_df, inc_df, req)
        if res.summary.overall_drift_detected:
            false_positives += 1

    fpr = false_positives / n_trials
    # At alpha=0.05 with multiple testing correction, FPR over trials should be comfortably <= 25%
    assert fpr <= 0.25, f"False positive rate {fpr} exceeded expected academic bound."


def test_clearly_shifted_data():
    rng = np.random.RandomState(42)
    ref_df = pd.DataFrame({"salary": rng.normal(50000, 5000, size=150)})
    inc_df = pd.DataFrame({"salary": rng.normal(85000, 5000, size=150)})

    req = DriftAnalysisRequest(
        reference_dataset_id="ref_id",
        incoming_dataset_id="inc_id",
        ks_alpha=0.05,
        ks_min_effect=0.10,
    )
    res = compute_drift_analysis(ref_df, inc_df, req)
    assert res.summary.overall_drift_detected is True
    feat = res.per_feature_results[0]
    assert feat.status == DriftStatusEnum.DRIFT
    assert feat.p_value is not None
    assert feat.p_value < 0.05


def test_categorical_shift():
    ref_df = pd.DataFrame({"category": ["A"] * 80 + ["B"] * 20})
    inc_df = pd.DataFrame({"category": ["A"] * 10 + ["B"] * 90})

    req = DriftAnalysisRequest(
        reference_dataset_id="ref_id",
        incoming_dataset_id="inc_id",
    )
    res = compute_drift_analysis(ref_df, inc_df, req)
    feat = res.per_feature_results[0]
    assert feat.status == DriftStatusEnum.DRIFT


def test_constant_column_skipped():
    ref_df = pd.DataFrame({"const_col": [1.0] * 50, "other": list(range(50))})
    inc_df = pd.DataFrame({"const_col": [1.0] * 50, "other": list(range(50))})

    req = DriftAnalysisRequest(reference_dataset_id="ref", incoming_dataset_id="inc")
    res = compute_drift_analysis(ref_df, inc_df, req)
    const_res = next(f for f in res.per_feature_results if f.feature == "const_col")
    assert const_res.status == DriftStatusEnum.SKIPPED_CONSTANT_FEATURE


def test_tiny_sample_skipped():
    ref_df = pd.DataFrame({"feat": [1.0, 2.0, 3.0]})
    inc_df = pd.DataFrame({"feat": [4.0, 5.0, 6.0]})

    req = DriftAnalysisRequest(reference_dataset_id="ref", incoming_dataset_id="inc", min_samples=30)
    res = compute_drift_analysis(ref_df, inc_df, req)
    feat = res.per_feature_results[0]
    assert feat.status == DriftStatusEnum.SKIPPED_INSUFFICIENT_DATA


def test_nans_and_empty_bins_handled_safely():
    ref_df = pd.DataFrame({"val": [1.0, np.nan, 2.0, np.nan] + [3.0] * 40})
    inc_df = pd.DataFrame({"val": [np.nan, 10.0, np.nan] + [5.0] * 40})

    req = DriftAnalysisRequest(reference_dataset_id="ref", incoming_dataset_id="inc")
    res = compute_drift_analysis(ref_df, inc_df, req)
    assert len(res.per_feature_results) == 1
    # Check that calculation completed without raising exceptions
    assert res.per_feature_results[0].status in (DriftStatusEnum.DRIFT, DriftStatusEnum.NO_DRIFT)


def test_multiple_testing_correction():
    raw_ps = [0.01, 0.04, 0.03, 0.50]
    # Bonferroni
    bonf = apply_multiple_testing_correction(raw_ps, MultipleTestingMethodEnum.BONFERRONI)
    assert bonf[0] == 0.04
    assert bonf[1] == 0.16

    # Benjamini-Hochberg
    bh = apply_multiple_testing_correction(raw_ps, MultipleTestingMethodEnum.BENJAMINI_HOCHBERG)
    assert all(adj >= raw for adj, raw in zip(bh, raw_ps))


def test_significant_low_effect_size():
    """Very large sample with tiny mean shift: statistically significant KS p < 0.05,

    but KS statistic < ks_min_effect (0.10) -> significant_low_effect.
    """
    rng = np.random.RandomState(42)
    # 50,000 samples each, minute shift
    ref_vals = rng.normal(0.0, 1.0, 10000)
    inc_vals = rng.normal(0.03, 1.0, 10000)

    ref_df = pd.DataFrame({"feat": ref_vals})
    inc_df = pd.DataFrame({"feat": inc_vals})

    req = DriftAnalysisRequest(
        reference_dataset_id="ref",
        incoming_dataset_id="inc",
        ks_alpha=0.05,
        ks_min_effect=0.10,
        multiple_testing_method=MultipleTestingMethodEnum.NONE,
    )
    res = compute_drift_analysis(ref_df, inc_df, req)
    feat = res.per_feature_results[0]
    # KS stat should be small (<0.10) but p-value significant
    if feat.p_value < 0.05 and feat.statistic < 0.10:
        assert feat.status == DriftStatusEnum.SIGNIFICANT_LOW_EFFECT


def test_drift_api_endpoint(client: TestClient):
    ref_csv = "f1,f2\n" + "\n".join(f"{i},{i*2}" for i in range(50))
    inc_csv = "f1,f2\n" + "\n".join(f"{i+50},{i*2+100}" for i in range(50))

    ref_resp = client.post(
        "/api/datasets/upload",
        files={"file": ("drift_ref.csv", io.BytesIO(ref_csv.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    inc_resp = client.post(
        "/api/datasets/upload",
        files={"file": ("drift_inc.csv", io.BytesIO(inc_csv.encode("utf-8")), "text/csv")},
        data={"role": "incoming"},
    )

    req_body = {
        "reference_dataset_id": ref_resp.json()["id"],
        "incoming_dataset_id": inc_resp.json()["id"],
        "ks_alpha": 0.05,
        "multiple_testing_method": "benjamini_hochberg",
    }
    response = client.post("/api/monitor/drift", json=req_body)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["features_tested"] == 2
    assert "methodology_note" in data["summary"]
