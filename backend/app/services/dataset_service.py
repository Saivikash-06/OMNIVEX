import csv
import io
import os
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import (
    NotFoundError,
    PayloadTooLargeError,
    SecurityViolationError,
    UnsupportedMediaTypeError,
    ValidationAppError,
)
from backend.app.core.security import (
    compute_sha256,
    generate_safe_filename,
    resolve_safe_path,
    sanitize_display_filename,
)
from backend.app.database.models import DatasetModel
from backend.app.schemas.common import DatasetRole
from backend.app.schemas.dataset import (
    ColumnSchema,
    DataQualitySummary,
    DatasetSchemaInfo,
    SchemaValidationIssue,
)


def classify_dtype(series: pd.Series) -> str:
    """Classify a pandas Series into numeric, categorical, boolean, or datetime."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical"


def infer_dataset_schema(df: pd.DataFrame) -> DatasetSchemaInfo:
    """Infer column schemas, types, nulls, and ranges from DataFrame."""
    columns_info = []
    total_rows = len(df)

    for col in df.columns:
        series = df[col]
        dtype_class = classify_dtype(series)
        null_count = int(series.isnull().sum())
        null_pct = float(null_count / total_rows) if total_rows > 0 else 0.0
        unique_cnt = int(series.nunique(dropna=True))

        min_val = None
        max_val = None
        cats = None

        if dtype_class == "numeric":
            valid_nums = series.dropna()
            if len(valid_nums) > 0:
                min_val = float(valid_nums.min())
                max_val = float(valid_nums.max())
        elif dtype_class in ("categorical", "boolean"):
            # Sample up to top 50 unique string representations
            cats = [str(x) for x in series.dropna().unique()[:50]]

        columns_info.append(
            ColumnSchema(
                name=str(col),
                dtype_class=dtype_class,
                pandas_dtype=str(series.dtype),
                null_count=null_count,
                null_percentage=round(null_pct, 4),
                unique_count=unique_cnt,
                min_value=min_val,
                max_value=max_val,
                categories=cats,
            )
        )

    return DatasetSchemaInfo(
        columns=columns_info,
        total_rows=total_rows,
        total_columns=len(df.columns),
    )


def validate_csv_content_and_stream_save(
    file_stream: BinaryIO,
    destination_path: Path,
    max_bytes: Optional[int] = None,
) -> int:
    """Stream file in chunks, enforce max size, reject binary (NUL bytes),

    and write to destination_path.
    """
    if max_bytes is None:
        max_bytes = settings.MAX_UPLOAD_SIZE_BYTES

    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KB
    has_checked_header = False

    with open(destination_path, "wb") as out_f:
        while chunk := file_stream.read(chunk_size):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                out_f.close()
                if destination_path.exists():
                    destination_path.unlink(missing_ok=True)
                raise PayloadTooLargeError(
                    f"File exceeds maximum upload size of {max_bytes / (1024*1024):.1f} MB."
                )

            # Check for NUL byte (binary content)
            if b"\x00" in chunk:
                out_f.close()
                if destination_path.exists():
                    destination_path.unlink(missing_ok=True)
                raise UnsupportedMediaTypeError("Binary content detected. Only valid text CSV is allowed.")

            out_f.write(chunk)

    if total_bytes == 0:
        if destination_path.exists():
            destination_path.unlink(missing_ok=True)
        raise ValidationAppError("Uploaded file is empty.")

    return total_bytes


def read_and_validate_csv_dataframe(file_path: Path) -> pd.DataFrame:
    """Read CSV with strict bounds, validating non-empty, row/column bounds, and unique columns."""
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            raw_header = next(reader, None)
    except Exception as exc:
        raise ValidationAppError(f"Failed to read CSV header: {str(exc)}")

    if not raw_header:
        raise ValidationAppError("CSV header is missing or empty.")

    col_names = [str(c).strip() for c in raw_header]
    for c in col_names:
        if not c:
            raise ValidationAppError("Empty column name detected in CSV header.")

    if len(col_names) != len(set(col_names)):
        duplicates = [c for c in col_names if col_names.count(c) > 1]
        raise ValidationAppError(f"Duplicate column names detected: {list(set(duplicates))}")

    if len(col_names) < 2:
        raise ValidationAppError("CSV must contain at least 2 columns.")

    if len(col_names) > settings.MAX_COLUMNS:
        raise ValidationAppError(f"Dataset exceeds maximum allowed columns ({settings.MAX_COLUMNS}).")

    try:
        df = pd.read_csv(
            file_path,
            nrows=settings.MAX_ROWS + 1,
            encoding="utf-8-sig",
        )
    except Exception as exc:
        raise ValidationAppError(f"Failed to parse CSV file: {str(exc)}")

    if len(df) == 0:
        raise ValidationAppError("CSV must contain at least 1 row of data.")

    if len(df) > settings.MAX_ROWS:
        raise ValidationAppError(f"Dataset exceeds maximum allowed rows ({settings.MAX_ROWS}).")

    df.columns = col_names
    return df


def save_dataset(
    db: Session,
    file_stream: BinaryIO,
    original_filename: str,
    role: DatasetRole,
) -> DatasetModel:
    """Process uploaded dataset, validate, compute schema, and persist metadata."""
    if not original_filename.lower().endswith(".csv"):
        raise UnsupportedMediaTypeError("Invalid file extension. Only .csv files are supported.")

    safe_original_name = sanitize_display_filename(original_filename)
    stored_filename = generate_safe_filename(".csv")
    stored_path = resolve_safe_path(settings.UPLOAD_DIR, stored_filename)

    # Stream file to disk with strict size and binary validation
    size_bytes = validate_csv_content_and_stream_save(file_stream, stored_path)

    # Compute hash and validate parseability
    sha256_hash = compute_sha256(stored_path)

    try:
        df = read_and_validate_csv_dataframe(stored_path)
    except Exception:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise

    schema_info = infer_dataset_schema(df)

    dataset_record = DatasetModel(
        name=safe_original_name,
        filename=stored_filename,
        file_path=str(stored_path),
        size_bytes=size_bytes,
        sha256=sha256_hash,
        row_count=len(df),
        column_count=len(df.columns),
        schema_json=schema_info.model_dump(),
        role=role.value,
    )

    db.add(dataset_record)
    db.commit()
    db.refresh(dataset_record)
    return dataset_record


def get_dataset_by_id(db: Session, dataset_id: str) -> DatasetModel:
    """Retrieve dataset record or raise NotFoundError."""
    dataset = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
    if not dataset:
        raise NotFoundError("Dataset", dataset_id)
    return dataset


def load_dataset_dataframe(dataset: DatasetModel) -> pd.DataFrame:
    """Load DataFrame from stored dataset record with safe path verification."""
    path = resolve_safe_path(settings.UPLOAD_DIR, dataset.filename)
    if not path.exists():
        raise NotFoundError("Dataset file on disk", dataset.filename)
    return pd.read_csv(path, encoding="utf-8-sig")


def validate_incoming_against_reference(
    ref_schema: DatasetSchemaInfo,
    incoming_df: pd.DataFrame,
    target_column: Optional[str] = None,
) -> Tuple[bool, List[SchemaValidationIssue], Optional[DataQualitySummary]]:
    """Validate incoming DataFrame against reference schema.

    Returns (is_valid, issues, quality_summary).
    """
    issues: List[SchemaValidationIssue] = []
    ref_cols_map = {col.name: col for col in ref_schema.columns}

    # Expected features (exclude target if target is not mandatory in incoming)
    expected_cols = set(ref_cols_map.keys())
    incoming_cols = set(incoming_df.columns)

    # If target is specified and missing in incoming, that's allowed (e.g. unlabelled inference)
    missing = expected_cols - incoming_cols
    if target_column and target_column in missing:
        missing.remove(target_column)

    if missing:
        for m in sorted(missing):
            issues.append(
                SchemaValidationIssue(
                    category="missing_columns",
                    column=m,
                    message=f"Required column '{m}' is missing from incoming data.",
                )
            )

    unexpected = incoming_cols - expected_cols
    if unexpected:
        for u in sorted(unexpected):
            issues.append(
                SchemaValidationIssue(
                    category="unexpected_columns",
                    column=u,
                    message=f"Unexpected column '{u}' found in incoming data that is not in reference schema.",
                )
            )

    # Check dtypes and excessive missing values for shared columns
    common_cols = expected_cols.intersection(incoming_cols)
    missing_value_rates: Dict[str, float] = {}
    unseen_category_rates: Dict[str, float] = {}
    out_of_range_rates: Dict[str, float] = {}

    for col in common_cols:
        ref_col = ref_cols_map[col]
        series = incoming_df[col]
        total_n = len(series)
        null_n = int(series.isnull().sum())
        null_rate = float(null_n / total_n) if total_n > 0 else 0.0
        missing_value_rates[col] = round(null_rate, 4)

        # Flag excessive nulls (> 50%)
        if null_rate > 0.50:
            issues.append(
                SchemaValidationIssue(
                    category="excessive_nulls",
                    column=col,
                    message=f"Column '{col}' has excessive missing values ({null_rate*100:.1f}%).",
                    details={"null_rate": null_rate},
                )
            )

        inc_dtype = classify_dtype(series)
        if ref_col.dtype_class == "numeric" and inc_dtype != "numeric":
            issues.append(
                SchemaValidationIssue(
                    category="incompatible_dtypes",
                    column=col,
                    message=f"Column '{col}' expected numeric type, but arrived as {inc_dtype}.",
                    details={"expected": "numeric", "actual": inc_dtype},
                )
            )

        # Unseen categories
        if ref_col.dtype_class in ("categorical", "boolean") and ref_col.categories:
            known_cats = set(ref_col.categories)
            incoming_cats = series.dropna().astype(str)
            if len(incoming_cats) > 0:
                unseen = [v for v in incoming_cats if v not in known_cats]
                unseen_rate = len(unseen) / len(incoming_cats)
                unseen_category_rates[col] = round(unseen_rate, 4)

        # Out-of-range rates for numeric (only if incoming column is numeric)
        if ref_col.dtype_class == "numeric" and inc_dtype == "numeric" and ref_col.min_value is not None and ref_col.max_value is not None:
            valid_nums = pd.to_numeric(series, errors="coerce").dropna()
            if len(valid_nums) > 0:
                out_of_range = valid_nums[
                    (valid_nums < ref_col.min_value) | (valid_nums > ref_col.max_value)
                ]
                out_rate = len(out_of_range) / len(valid_nums)
                out_of_range_rates[col] = round(out_rate, 4)

    # Compute overall quality score (1.0 = perfect, penalized by missingness and out of range)
    avg_missing = np.mean(list(missing_value_rates.values())) if missing_value_rates else 0.0
    avg_unseen = np.mean(list(unseen_category_rates.values())) if unseen_category_rates else 0.0
    quality_score = max(0.0, min(1.0, 1.0 - (avg_missing * 0.6 + avg_unseen * 0.4)))

    quality_summary = DataQualitySummary(
        missing_value_rates=missing_value_rates,
        unseen_category_rates=unseen_category_rates,
        out_of_range_rates=out_of_range_rates,
        overall_quality_score=round(float(quality_score), 4),
    )

    # Valid if no missing columns and no incompatible dtypes
    critical_issues = [i for i in issues if i.category in ("missing_columns", "incompatible_dtypes")]
    is_valid = len(critical_issues) == 0

    return is_valid, issues, quality_summary


def build_preprocessor_pipeline(
    df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[ColumnTransformer, List[str], List[str]]:
    """Build and fit a ColumnTransformer on reference DataFrame features ONLY.

    Median imputation for numeric + StandardScaler.
    Most frequent imputation for categorical + OneHotEncoder with handle_unknown='ignore'.
    """
    numeric_features = []
    categorical_features = []

    for col in feature_cols:
        series = df[col]
        dtype_class = classify_dtype(series)
        if dtype_class == "numeric":
            numeric_features.append(col)
        else:
            categorical_features.append(col)

    transformers = []
    if numeric_features:
        numeric_transformer = ColumnTransformer(
            transformers=[
                (
                    "imputer",
                    SimpleImputer(strategy="median"),
                    list(range(len(numeric_features))),
                )
            ]
        )
        transformers.append(("num", SimpleImputer(strategy="median"), numeric_features))

    if categorical_features:
        categorical_transformer = ColumnTransformer(
            transformers=[
                (
                    "cat_impute",
                    SimpleImputer(strategy="most_frequent"),
                    list(range(len(categorical_features))),
                )
            ]
        )
        transformers.append(
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                categorical_features,
            )
        )

    # Use ColumnTransformer with handle_unknown safely
    preprocessor = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )
    preprocessor.fit(df[feature_cols])

    return preprocessor, numeric_features, categorical_features
