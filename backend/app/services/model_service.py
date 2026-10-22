import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import (
    NotFoundError,
    SecurityViolationError,
    ValidationAppError,
)
from backend.app.core.security import (
    compute_sha256,
    generate_safe_filename,
    resolve_safe_path,
    verify_file_hash,
)
from backend.app.database.models import DatasetModel, TrainedModel
from backend.app.schemas.common import AlgorithmEnum
from backend.app.schemas.model import (
    BaselineMetrics,
    PredictResponse,
    TrainModelRequest,
    TrainedModelResponse,
)
from backend.app.services.dataset_service import (
    build_preprocessor_pipeline,
    classify_dtype,
    get_dataset_by_id,
    load_dataset_dataframe,
)


def get_library_versions() -> Dict[str, str]:
    """Capture runtime versions of core scientific libraries for reproducibility."""
    return {
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }


def validate_and_sanitize_hyperparameters(
    algorithm: AlgorithmEnum,
    raw_params: Optional[Dict[str, Any]],
    random_seed: int,
) -> Dict[str, Any]:
    """Validate hyperparameter allow-lists with safe bounds."""
    params = raw_params.copy() if raw_params else {}
    sanitized: Dict[str, Any] = {}

    if algorithm == AlgorithmEnum.LOGISTIC_REGRESSION:
        c_val = params.get("C", 1.0)
        if not isinstance(c_val, (int, float)) or c_val <= 0 or c_val > 100:
            raise ValidationAppError("Logistic Regression 'C' must be a float between 0 and 100.")
        sanitized["C"] = float(c_val)

        max_iter = params.get("max_iter", 200)
        if not isinstance(max_iter, int) or max_iter < 50 or max_iter > 2000:
            raise ValidationAppError("Logistic Regression 'max_iter' must be an integer between 50 and 2000.")
        sanitized["max_iter"] = max_iter
        sanitized["random_state"] = random_seed

    elif algorithm == AlgorithmEnum.RANDOM_FOREST:
        n_estimators = params.get("n_estimators", 100)
        if not isinstance(n_estimators, int) or n_estimators < 10 or n_estimators > 500:
            raise ValidationAppError("Random Forest 'n_estimators' must be an integer between 10 and 500.")
        sanitized["n_estimators"] = n_estimators

        max_depth = params.get("max_depth", None)
        if max_depth is not None:
            if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 50:
                raise ValidationAppError("Random Forest 'max_depth' must be an integer between 1 and 50.")
            sanitized["max_depth"] = max_depth

        sanitized["random_state"] = random_seed

    elif algorithm == AlgorithmEnum.GRADIENT_BOOSTING:
        n_estimators = params.get("n_estimators", 100)
        if not isinstance(n_estimators, int) or n_estimators < 10 or n_estimators > 500:
            raise ValidationAppError("Gradient Boosting 'n_estimators' must be between 10 and 500.")
        sanitized["n_estimators"] = n_estimators

        lr = params.get("learning_rate", 0.1)
        if not isinstance(lr, (int, float)) or lr <= 0 or lr > 1.0:
            raise ValidationAppError("Gradient Boosting 'learning_rate' must be between 0 and 1.0.")
        sanitized["learning_rate"] = float(lr)

        sanitized["random_state"] = random_seed

    elif algorithm == AlgorithmEnum.DECISION_TREE:
        max_depth = params.get("max_depth", None)
        if max_depth is not None:
            if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 50:
                raise ValidationAppError("Decision Tree 'max_depth' must be between 1 and 50.")
            sanitized["max_depth"] = max_depth

        sanitized["random_state"] = random_seed

    return sanitized


def create_estimator(algorithm: AlgorithmEnum, params: Dict[str, Any]):
    """Instantiate scikit-learn estimator from allow-list."""
    if algorithm == AlgorithmEnum.LOGISTIC_REGRESSION:
        return LogisticRegression(**params)
    elif algorithm == AlgorithmEnum.RANDOM_FOREST:
        return RandomForestClassifier(**params)
    elif algorithm == AlgorithmEnum.GRADIENT_BOOSTING:
        return GradientBoostingClassifier(**params)
    elif algorithm == AlgorithmEnum.DECISION_TREE:
        return DecisionTreeClassifier(**params)
    raise ValidationAppError(f"Unsupported algorithm '{algorithm}'.")


def train_model(db: Session, request: TrainModelRequest) -> TrainedModel:
    """Train pipeline on reference dataset, evaluate honest baseline on validation set,

    and safely persist hash-verified artifact.
    """
    dataset_record = get_dataset_by_id(db, request.dataset_id)
    df = load_dataset_dataframe(dataset_record)

    # Validate target column
    if request.target_column not in df.columns:
        raise ValidationAppError(f"Target column '{request.target_column}' does not exist in dataset.")

    # Determine feature columns
    if request.feature_columns:
        feature_cols = request.feature_columns
        for f in feature_cols:
            if f not in df.columns:
                raise ValidationAppError(f"Feature column '{f}' does not exist in dataset.")
    else:
        feature_cols = [c for c in df.columns if c != request.target_column]

    if not feature_cols:
        raise ValidationAppError("At least one feature column is required.")

    # Reject target leakage
    if request.target_column in feature_cols:
        raise ValidationAppError("Target leakage detected: target column cannot be included in feature set.")

    # Clean target: drop rows with missing target
    valid_mask = df[request.target_column].notnull()
    clean_df = df[valid_mask]
    y_raw = clean_df[request.target_column].astype(str)
    class_counts = y_raw.value_counts()

    if len(class_counts) < 2:
        raise ValidationAppError("Target must contain at least 2 distinct classes.")

    for cls_name, count in class_counts.items():
        if count < 2:
            raise ValidationAppError(f"Target class '{cls_name}' has fewer than 2 samples; cannot split.")

    X = clean_df[feature_cols]
    y = y_raw.values
    class_labels = sorted(list(class_counts.keys()))

    # Stratified split where possible
    try:
        X_train, X_val, y_train, y_val = train_test_split(
            X,
            y,
            test_size=request.test_size,
            random_state=request.random_seed,
            stratify=y,
        )
    except Exception:
        # Fallback to unstratified split if stratification fails due to small class counts
        X_train, X_val, y_train, y_val = train_test_split(
            X,
            y,
            test_size=request.test_size,
            random_state=request.random_seed,
        )

    # Sanitize hyperparameters
    sanitized_params = validate_and_sanitize_hyperparameters(
        request.algorithm,
        request.hyperparameters,
        request.random_seed,
    )

    # Build preprocessing ColumnTransformer fit on reference training data ONLY
    preprocessor, num_features, cat_features = build_preprocessor_pipeline(X_train, feature_cols)
    estimator = create_estimator(request.algorithm, sanitized_params)

    # Combine into single pipeline
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", estimator),
        ]
    )

    # Train on training partition
    pipeline.fit(X_train, y_train)

    # Compute baseline metrics on held-out validation split
    y_pred = pipeline.predict(X_val)
    acc = float(accuracy_score(y_val, y_pred))
    prec = float(precision_score(y_val, y_pred, average="macro", zero_division=0))
    rec = float(recall_score(y_val, y_pred, average="macro", zero_division=0))
    f1 = float(f1_score(y_val, y_pred, average="macro", zero_division=0))
    cm = confusion_matrix(y_val, y_pred, labels=class_labels).tolist()

    baseline_metrics = BaselineMetrics(
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        f1_average="macro",
        confusion_matrix=cm,
        sample_size=len(y_val),
    )

    # Persist model artifact securely
    artifact_filename = generate_safe_filename(".joblib")
    artifact_path = resolve_safe_path(settings.MODEL_DIR, artifact_filename)

    # Save artifact using joblib
    joblib.dump(pipeline, artifact_path)

    # Compute SHA-256 hash immediately after save
    artifact_hash = compute_sha256(artifact_path)

    feature_dtypes = {col: classify_dtype(clean_df[col]) for col in feature_cols}

    model_record = TrainedModel(
        name=request.name,
        algorithm=request.algorithm.value,
        hyperparameters=sanitized_params,
        feature_names=feature_cols,
        feature_dtypes=feature_dtypes,
        target_column=request.target_column,
        class_labels=class_labels,
        training_dataset_id=dataset_record.id,
        training_dataset_hash=dataset_record.sha256,
        random_seed=request.random_seed,
        library_versions=get_library_versions(),
        baseline_metrics=baseline_metrics.model_dump(),
        artifact_filename=artifact_filename,
        artifact_path=str(artifact_path),
        artifact_sha256=artifact_hash,
    )

    db.add(model_record)
    db.commit()
    db.refresh(model_record)
    return model_record


def load_model_pipeline(model_record: TrainedModel) -> Pipeline:
    """Verify SHA-256 hash before loading model pipeline from disk."""
    artifact_path = resolve_safe_path(settings.MODEL_DIR, model_record.artifact_filename)

    if not artifact_path.exists():
        raise NotFoundError("Model artifact on disk", model_record.artifact_filename)

    if not verify_file_hash(artifact_path, model_record.artifact_sha256):
        raise SecurityViolationError(
            "Model integrity check failed: stored artifact SHA-256 does not match recorded hash. Refusing to load."
        )

    return joblib.load(artifact_path)


def predict_dataset(
    db: Session,
    model_id: str,
    dataset_id: str,
) -> PredictResponse:
    """Predict on dataset after verifying feature compatibility."""
    model_record = db.query(TrainedModel).filter(TrainedModel.id == model_id).first()
    if not model_record:
        raise NotFoundError("Model", model_id)

    dataset_record = get_dataset_by_id(db, dataset_id)
    df = load_dataset_dataframe(dataset_record)

    # Validate feature compatibility
    required_features = model_record.feature_names
    missing_features = [f for f in required_features if f not in df.columns]
    if missing_features:
        raise ValidationAppError(
            f"Dataset is missing required feature columns for prediction: {missing_features}"
        )

    pipeline = load_model_pipeline(model_record)

    # Perform inference
    X = df[required_features]
    predictions = pipeline.predict(X).tolist()

    probabilities = None
    if hasattr(pipeline, "predict_proba"):
        try:
            probabilities = pipeline.predict_proba(X).tolist()
        except Exception:
            probabilities = None

    return PredictResponse(
        model_id=model_id,
        dataset_id=dataset_id,
        sample_count=len(df),
        predictions=[str(p) for p in predictions],
        probabilities=probabilities,
        feature_names=required_features,
    )
