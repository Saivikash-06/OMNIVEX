from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sqlalchemy.orm import Session

from backend.app.core.errors import NotFoundError, ValidationAppError
from backend.app.database.models import TrainedModel
from backend.app.schemas.common import MetricAverageEnum
from backend.app.schemas.performance import (
    ConfidenceInterval,
    PerformanceAnalysisRequest,
    PerformanceMetricsDetail,
)
from backend.app.services.dataset_service import get_dataset_by_id, load_dataset_dataframe
from backend.app.services.model_service import load_model_pipeline


def bootstrap_metric_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_func,
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> ConfidenceInterval:
    """Compute empirical bootstrap confidence interval for a metric."""
    n = len(y_true)
    if n < 5:
        return ConfidenceInterval(lower=0.0, upper=1.0, confidence_level=1.0 - alpha)

    rng = np.random.RandomState(seed)
    scores = np.empty(n_resamples)

    for i in range(n_resamples):
        indices = rng.randint(0, n, size=n)
        scores[i] = metric_func(y_true[indices], y_pred[indices])

    lower = float(np.percentile(scores, (alpha / 2.0) * 100))
    upper = float(np.percentile(scores, (1.0 - alpha / 2.0) * 100))
    return ConfidenceInterval(
        lower=round(max(0.0, lower), 4),
        upper=round(min(1.0, upper), 4),
        confidence_level=1.0 - alpha,
    )


def compute_performance_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    training_classes: List[str],
    baseline_metrics: Dict[str, float],
    request: PerformanceAnalysisRequest,
) -> PerformanceMetricsDetail:
    """Pure function calculating classification metrics, deltas against baseline,

    and bootstrap confidence intervals.
    """
    sample_size = len(y_true)
    y_true_str = np.array([str(y) for y in y_true])
    y_pred_str = np.array([str(p) for p in y_pred])

    if sample_size < request.min_samples:
        return PerformanceMetricsDetail(
            sample_size=sample_size,
            status="insufficient_data",
            note=f"Sample size ({sample_size}) is below minimum requirement ({request.min_samples}).",
        )

    # Class presence check
    unique_true = set(y_true_str)
    absent = [c for c in training_classes if c not in unique_true]
    unseen = [c for c in unique_true if c not in set(training_classes)]

    avg_mode = request.f1_average.value
    pos_lbl = request.pos_label if avg_mode == "binary" else None

    acc = float(accuracy_score(y_true_str, y_pred_str))
    prec = float(
        precision_score(
            y_true_str,
            y_pred_str,
            average=avg_mode,
            pos_label=pos_lbl,
            zero_division=0,
        )
    )
    rec = float(
        recall_score(
            y_true_str,
            y_pred_str,
            average=avg_mode,
            pos_label=pos_lbl,
            zero_division=0,
        )
    )
    f1 = float(
        f1_score(
            y_true_str,
            y_pred_str,
            average=avg_mode,
            pos_label=pos_lbl,
            zero_division=0,
        )
    )

    # Confusion matrix with fixed training class order
    cm = confusion_matrix(y_true_str, y_pred_str, labels=training_classes).tolist()

    # Baseline deltas
    base_acc = baseline_metrics.get("accuracy", 1.0)
    base_f1 = baseline_metrics.get("f1", 1.0)

    abs_diff_acc = acc - base_acc
    rel_diff_acc = abs_diff_acc / base_acc if base_acc > 0 else 0.0

    abs_diff_f1 = f1 - base_f1
    rel_diff_f1 = abs_diff_f1 / base_f1 if base_f1 > 0 else 0.0

    # Bootstrap CIs
    acc_ci = bootstrap_metric_ci(
        y_true_str,
        y_pred_str,
        lambda yt, yp: accuracy_score(yt, yp),
        n_resamples=request.bootstrap_resamples,
        seed=request.random_seed,
    )
    f1_ci = bootstrap_metric_ci(
        y_true_str,
        y_pred_str,
        lambda yt, yp: f1_score(yt, yp, average=avg_mode, pos_label=pos_lbl, zero_division=0),
        n_resamples=request.bootstrap_resamples,
        seed=request.random_seed + 1,
    )

    # Flag degradation: drop exceeds tolerance AND baseline is outside the CI (or drop is severe)
    acc_drop = -abs_diff_acc
    f1_drop = -abs_diff_f1
    degradation = False

    if acc_drop > request.performance_drop_tolerance and (base_acc > acc_ci.upper or acc_drop > request.performance_drop_tolerance * 1.5):
        degradation = True
    elif f1_drop > request.performance_drop_tolerance and (base_f1 > f1_ci.upper or f1_drop > request.performance_drop_tolerance * 1.5):
        degradation = True

    note = "Evaluation completed."
    if absent:
        note += f" Classes absent from batch: {absent}."
    if unseen:
        note += f" Unseen classes detected: {unseen}."

    return PerformanceMetricsDetail(
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        f1_average=request.f1_average,
        confusion_matrix=cm,
        class_labels=training_classes,
        abs_diff_accuracy=round(abs_diff_acc, 4),
        rel_diff_accuracy=round(rel_diff_acc, 4),
        abs_diff_f1=round(abs_diff_f1, 4),
        rel_diff_f1=round(rel_diff_f1, 4),
        accuracy_ci=acc_ci,
        f1_ci=f1_ci,
        sample_size=sample_size,
        degradation_flagged=degradation,
        status="evaluated",
        absent_classes=absent,
        unseen_classes=unseen,
        note=note,
    )


def evaluate_dataset_performance(
    db: Session,
    request: PerformanceAnalysisRequest,
) -> PerformanceMetricsDetail:
    """Evaluate performance of model on incoming dataset if labels are available."""
    model_record = db.query(TrainedModel).filter(TrainedModel.id == request.model_id).first()
    if not model_record:
        raise NotFoundError("Model", request.model_id)

    dataset_record = get_dataset_by_id(db, request.dataset_id)
    df = load_dataset_dataframe(dataset_record)

    label_col = request.label_column or model_record.target_column

    # If label column is not present or all null -> labels_unavailable
    if label_col not in df.columns or df[label_col].isnull().all():
        return PerformanceMetricsDetail(
            sample_size=len(df),
            status="labels_unavailable",
            note="Labels are unavailable in the incoming dataset. Model accuracy cannot be evaluated.",
        )

    # Check required feature columns
    required_features = model_record.feature_names
    missing = [f for f in required_features if f not in df.columns]
    if missing:
        raise ValidationAppError(f"Missing required feature columns for model evaluation: {missing}")

    # Predict using verified pipeline
    pipeline = load_model_pipeline(model_record)
    valid_mask = df[label_col].notnull()
    eval_df = df[valid_mask]

    if len(eval_df) == 0:
        return PerformanceMetricsDetail(
            sample_size=0,
            status="labels_unavailable",
            note="No non-null labels found in label column.",
        )

    X_eval = eval_df[required_features]
    y_true = eval_df[label_col].values
    y_pred = pipeline.predict(X_eval)

    return compute_performance_metrics(
        y_true=y_true,
        y_pred=y_pred,
        training_classes=model_record.class_labels,
        baseline_metrics=model_record.baseline_metrics,
        request=request,
    )
