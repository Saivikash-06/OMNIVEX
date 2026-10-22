import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.common import DatasetRole, PaginatedResponse, StrictBaseModel


class ColumnSchema(StrictBaseModel):
    name: str
    dtype_class: str  # numeric, categorical, datetime, boolean
    pandas_dtype: str
    null_count: int
    null_percentage: float
    unique_count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    categories: Optional[List[str]] = None


class DatasetSchemaInfo(StrictBaseModel):
    columns: List[ColumnSchema]
    total_rows: int
    total_columns: int


class DatasetResponse(StrictBaseModel):
    id: str
    name: str
    filename: str
    size_bytes: int
    sha256: str
    row_count: int
    column_count: int
    role: DatasetRole
    schema_info: DatasetSchemaInfo
    created_at: datetime.datetime


class SchemaValidationIssue(StrictBaseModel):
    category: str  # missing_columns, unexpected_columns, incompatible_dtypes, excessive_nulls
    column: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None


class DataQualitySummary(StrictBaseModel):
    missing_value_rates: Dict[str, float]
    unseen_category_rates: Dict[str, float]
    out_of_range_rates: Dict[str, float]
    overall_quality_score: float  # 0.0 to 1.0


class ValidationResultResponse(StrictBaseModel):
    is_valid: bool
    issues: List[SchemaValidationIssue]
    quality_summary: Optional[DataQualitySummary] = None
    reference_dataset_id: str
    incoming_dataset_id: str
