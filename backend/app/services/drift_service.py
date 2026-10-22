import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from backend.app.schemas.common import (
    DriftStatusEnum,
    DriftTestNameEnum,
    MultipleTestingMethodEnum,
)
from backend.app.schemas.drift import (
    DriftAnalysisRequest,
    DriftAnalysisResponse,
    DriftFeatureResult,
    DriftSummary,
)
from backend.app.services.dataset_service import classify_dtype


def calculate_numerical_psi(
    ref_values: np.ndarray,
    inc_values: np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """Calculate Population Stability Index (PSI) for numerical arrays

    using reference quantiles as bin edges.
    """
    if len(ref_values) == 0 or len(inc_values) == 0:
        return 0.0

    # Determine unique quantiles
    quantiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(ref_values, quantiles)
    bin_edges = np.unique(bin_edges)

    # If low-cardinality data causes fewer than 2 edges
    if len(bin_edges) < 2:
        bin_edges = np.array([ref_values.min() - 1e-3, ref_values.max() + 1e-3])

    # Extend boundaries to cover min/max of incoming data
    bin_edges[0] = min(bin_edges[0], np.min(inc_values) - 1e-3)
    bin_edges[-1] = max(bin_edges[-1], np.max(inc_values) + 1e-3)

    # Histogram counts
    ref_counts, _ = np.histogram(ref_values, bins=bin_edges)
    inc_counts, _ = np.histogram(inc_values, bins=bin_edges)

    # Convert to proportions with smoothing epsilon to prevent division by zero or log(0)
    ref_props = (ref_counts + epsilon) / (np.sum(ref_counts) + epsilon * len(ref_counts))
    inc_props = (inc_counts + epsilon) / (np.sum(inc_counts) + epsilon * len(inc_counts))

    psi = np.sum((inc_props - ref_props) * np.log(inc_props / ref_props))
    return float(max(0.0, psi))


def calculate_categorical_psi(
    ref_series: pd.Series,
    inc_series: pd.Series,
    epsilon: float = 1e-4,
) -> float:
    """Calculate PSI for categorical data, grouping unseen incoming categories into __other__."""
    ref_clean = ref_series.dropna().astype(str)
    inc_clean = inc_series.dropna().astype(str)

    if len(ref_clean) == 0 or len(inc_clean) == 0:
        return 0.0

    ref_counts = ref_clean.value_counts(normalize=True).to_dict()
    known_cats = set(ref_counts.keys())

    # Map incoming unseen categories to '__other__'
    inc_mapped = inc_clean.apply(lambda x: x if x in known_cats else "__other__")
    inc_counts = inc_mapped.value_counts(normalize=True).to_dict()

    all_cats = list(known_cats) + ["__other__"]
    psi = 0.0

    for cat in all_cats:
        r_prop = ref_counts.get(cat, 0.0)
        i_prop = inc_counts.get(cat, 0.0)

        r_smoothed = (r_prop + epsilon) / (1.0 + epsilon * len(all_cats))
        i_smoothed = (i_prop + epsilon) / (1.0 + epsilon * len(all_cats))

        psi += (i_smoothed - r_smoothed) * math.log(i_smoothed / r_smoothed)

    return float(max(0.0, psi))


def apply_multiple_testing_correction(
    p_values: List[Optional[float]],
    method: MultipleTestingMethodEnum,
) -> List[Optional[float]]:
    """Adjust p-values using Benjamini-Hochberg (FDR) or Bonferroni."""
    n = sum(1 for p in p_values if p is not None)
    if n == 0 or method == MultipleTestingMethodEnum.NONE:
        return list(p_values)

    adjusted = [None] * len(p_values)
    valid_indices = [i for i, p in enumerate(p_values) if p is not None]
    raw_ps = [p_values[i] for i in valid_indices]

    if method == MultipleTestingMethodEnum.BONFERRONI:
        for idx, p in zip(valid_indices, raw_ps):
            adjusted[idx] = min(1.0, p * n)
    elif method == MultipleTestingMethodEnum.BENJAMINI_HOCHBERG:
        # Sort by p-value ascending
        sorted_pairs = sorted(enumerate(raw_ps), key=lambda x: x[1])
        # Benjamini-Hochberg adjustment
        adj_vals = [0.0] * n
        running_min = 1.0
        for rank in range(n, 0, -1):
            original_idx, p_val = sorted_pairs[rank - 1]
            q_val = min(1.0, (p_val * n) / rank)
            running_min = min(running_min, q_val)
            adj_vals[rank - 1] = running_min

        for (orig_rank, (orig_i, _)), adj_val in zip(enumerate(sorted_pairs), adj_vals):
            orig_idx_in_valid = orig_i
            global_idx = valid_indices[orig_idx_in_valid]
            adjusted[global_idx] = round(adj_val, 6)

    return adjusted


def compute_drift_analysis(
    ref_df: pd.DataFrame,
    inc_df: pd.DataFrame,
    request: DriftAnalysisRequest,
) -> DriftAnalysisResponse:
    """Pure function performing feature-by-feature drift detection and summary."""
    # Select candidate features
    all_ref_cols = list(ref_df.columns)
    if request.features_to_include:
        candidate_cols = [c for c in request.features_to_include if c in all_ref_cols and c in inc_df.columns]
    else:
        candidate_cols = [c for c in all_ref_cols if c in inc_df.columns]

    if request.features_to_exclude:
        candidate_cols = [c for c in candidate_cols if c not in request.features_to_exclude]

    prelim_results: List[Dict] = []

    for col in candidate_cols:
        ref_series = ref_df[col]
        inc_series = inc_df[col]
        ref_dtype = classify_dtype(ref_series)

        ref_clean = ref_series.dropna()
        inc_clean = inc_series.dropna()
        ref_n = len(ref_clean)
        inc_n = len(inc_clean)

        # Check sample size
        if ref_n < request.min_samples or inc_n < request.min_samples:
            prelim_results.append({
                "feature": col,
                "feature_type": ref_dtype,
                "test_name": "sample_check",
                "statistic": 0.0,
                "p_value": None,
                "threshold": request.ks_alpha,
                "status": DriftStatusEnum.SKIPPED_INSUFFICIENT_DATA,
                "reference_n": ref_n,
                "incoming_n": inc_n,
                "note": f"Insufficient non-null samples (ref={ref_n}, inc={inc_n}, min={request.min_samples}).",
            })
            continue

        # Check constant column
        if ref_clean.nunique() <= 1 and inc_clean.nunique() <= 1:
            prelim_results.append({
                "feature": col,
                "feature_type": ref_dtype,
                "test_name": "constant_check",
                "statistic": 0.0,
                "p_value": None,
                "threshold": request.ks_alpha,
                "status": DriftStatusEnum.SKIPPED_CONSTANT_FEATURE,
                "reference_n": ref_n,
                "incoming_n": inc_n,
                "note": "Feature is constant in both reference and incoming datasets.",
            })
            continue

        try:
            if ref_dtype == "numeric":
                ref_vals = pd.to_numeric(ref_clean, errors="coerce").dropna().values
                inc_vals = pd.to_numeric(inc_clean, errors="coerce").dropna().values

                if len(ref_vals) < request.min_samples or len(inc_vals) < request.min_samples:
                    prelim_results.append({
                        "feature": col,
                        "feature_type": "numeric",
                        "test_name": "sample_check",
                        "statistic": 0.0,
                        "p_value": None,
                        "threshold": request.ks_alpha,
                        "status": DriftStatusEnum.SKIPPED_INSUFFICIENT_DATA,
                        "reference_n": len(ref_vals),
                        "incoming_n": len(inc_vals),
                        "note": "Insufficient valid numeric samples after coercion.",
                    })
                    continue

                # KS 2-sample test
                ks_stat, ks_p = stats.ks_2samp(ref_vals, inc_vals)
                psi_val = calculate_numerical_psi(ref_vals, inc_vals)

                prelim_results.append({
                    "feature": col,
                    "feature_type": "numeric",
                    "test_name": DriftTestNameEnum.KS.value,
                    "statistic": float(ks_stat),
                    "psi_stat": float(psi_val),
                    "p_value": float(ks_p),
                    "threshold": request.ks_alpha,
                    "reference_n": len(ref_vals),
                    "incoming_n": len(inc_vals),
                    "note": f"KS statistic={ks_stat:.4f}, PSI={psi_val:.4f}",
                })
            else:
                # Categorical drift
                psi_val = calculate_categorical_psi(ref_clean, inc_clean)

                if request.use_chi_square_for_categorical:
                    # Contingency table
                    cats = list(set(ref_clean.astype(str)).union(set(inc_clean.astype(str))))
                    r_counts = ref_clean.astype(str).value_counts().reindex(cats, fill_value=0).values
                    i_counts = inc_clean.astype(str).value_counts().reindex(cats, fill_value=0).values

                    table = np.array([r_counts, i_counts])
                    try:
                        chi2, p_val, dof, ex = stats.chi2_contingency(table)
                        # Small expected count guard
                        low_expected = (ex < 5).sum() / ex.size
                        chi_note = f"Chi-square={chi2:.2f}, PSI={psi_val:.4f}"
                        if low_expected > 0.20:
                            chi_note += f" (Note: {low_expected*100:.0f}% expected cells < 5)"

                        prelim_results.append({
                            "feature": col,
                            "feature_type": "categorical",
                            "test_name": DriftTestNameEnum.CHI_SQUARE.value,
                            "statistic": float(chi2),
                            "psi_stat": float(psi_val),
                            "p_value": float(p_val),
                            "threshold": request.ks_alpha,
                            "reference_n": ref_n,
                            "incoming_n": inc_n,
                            "note": chi_note,
                        })
                    except Exception:
                        # Fallback to PSI alone
                        prelim_results.append({
                            "feature": col,
                            "feature_type": "categorical",
                            "test_name": DriftTestNameEnum.PSI.value,
                            "statistic": float(psi_val),
                            "psi_stat": float(psi_val),
                            "p_value": None,
                            "threshold": request.psi_moderate,
                            "reference_n": ref_n,
                            "incoming_n": inc_n,
                            "note": f"Categorical PSI={psi_val:.4f}",
                        })
                else:
                    prelim_results.append({
                        "feature": col,
                        "feature_type": "categorical",
                        "test_name": DriftTestNameEnum.PSI.value,
                        "statistic": float(psi_val),
                        "psi_stat": float(psi_val),
                        "p_value": None,
                        "threshold": request.psi_moderate,
                        "reference_n": ref_n,
                        "incoming_n": inc_n,
                        "note": f"Categorical PSI={psi_val:.4f}",
                    })
        except Exception as exc:
            prelim_results.append({
                "feature": col,
                "feature_type": ref_dtype,
                "test_name": "error",
                "statistic": 0.0,
                "p_value": None,
                "threshold": request.ks_alpha,
                "status": DriftStatusEnum.ERROR,
                "reference_n": ref_n,
                "incoming_n": inc_n,
                "note": f"Error calculating drift: {type(exc).__name__}",
            })

    # Multiple testing correction on p-values
    p_values_to_correct = [r.get("p_value") for r in prelim_results]
    adjusted_p_values = apply_multiple_testing_correction(
        p_values_to_correct,
        request.multiple_testing_method,
    )

    final_feature_results: List[DriftFeatureResult] = []
    features_drifted = 0
    features_tested = 0
    features_skipped = 0
    any_major_psi = False

    for item, adj_p in zip(prelim_results, adjusted_p_values):
        if "status" in item:
            # Already set to skipped or error
            final_feature_results.append(
                DriftFeatureResult(
                    feature=item["feature"],
                    feature_type=item["feature_type"],
                    test_name=item["test_name"],
                    statistic=item["statistic"],
                    p_value=item["p_value"],
                    adjusted_p_value=None,
                    threshold=item["threshold"],
                    status=item["status"],
                    reference_n=item["reference_n"],
                    incoming_n=item["incoming_n"],
                    note=item["note"],
                )
            )
            features_skipped += 1
            continue

        features_tested += 1
        stat = item["statistic"]
        raw_p = item["p_value"]
        psi_val = item.get("psi_stat", 0.0)
        test_name = item["test_name"]
        effective_p = adj_p if (adj_p is not None and request.multiple_testing_method != MultipleTestingMethodEnum.NONE) else raw_p

        status = DriftStatusEnum.NO_DRIFT
        if psi_val >= request.psi_major:
            any_major_psi = True

        if test_name == DriftTestNameEnum.KS.value:
            is_stat_sig = effective_p is not None and effective_p < request.ks_alpha
            if is_stat_sig:
                if stat < request.ks_min_effect:
                    status = DriftStatusEnum.SIGNIFICANT_LOW_EFFECT
                else:
                    status = DriftStatusEnum.DRIFT
            elif psi_val >= request.psi_major:
                status = DriftStatusEnum.DRIFT
        elif test_name == DriftTestNameEnum.CHI_SQUARE.value:
            is_stat_sig = effective_p is not None and effective_p < request.ks_alpha
            if is_stat_sig or psi_val >= request.psi_major:
                status = DriftStatusEnum.DRIFT
        elif test_name == DriftTestNameEnum.PSI.value:
            if stat >= request.psi_moderate:
                status = DriftStatusEnum.DRIFT

        if status == DriftStatusEnum.DRIFT:
            features_drifted += 1

        final_feature_results.append(
            DriftFeatureResult(
                feature=item["feature"],
                feature_type=item["feature_type"],
                test_name=test_name,
                statistic=round(stat, 6),
                p_value=round(raw_p, 6) if raw_p is not None else None,
                adjusted_p_value=round(adj_p, 6) if adj_p is not None else None,
                threshold=item["threshold"],
                status=status,
                reference_n=item["reference_n"],
                incoming_n=item["incoming_n"],
                note=item["note"],
            )
        )

    drift_ratio = float(features_drifted / features_tested) if features_tested > 0 else 0.0
    overall_drift = (drift_ratio >= request.drift_ratio_threshold) or any_major_psi

    summary = DriftSummary(
        features_tested=features_tested,
        features_skipped=features_skipped,
        features_drifted=features_drifted,
        drift_ratio=round(drift_ratio, 4),
        overall_drift_detected=overall_drift,
        multiple_testing_method=request.multiple_testing_method,
    )

    return DriftAnalysisResponse(
        reference_dataset_id=request.reference_dataset_id,
        incoming_dataset_id=request.incoming_dataset_id,
        per_feature_results=final_feature_results,
        summary=summary,
    )
