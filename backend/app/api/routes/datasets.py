from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_api_key
from backend.app.core.errors import ValidationAppError
from backend.app.database.models import DatasetModel
from backend.app.schemas.common import DatasetRole, PaginatedResponse
from backend.app.schemas.dataset import (
    DatasetResponse,
    DatasetSchemaInfo,
    ValidationResultResponse,
)
from backend.app.services.dataset_service import (
    get_dataset_by_id,
    load_dataset_dataframe,
    save_dataset,
    validate_incoming_against_reference,
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


def model_to_response(model: DatasetModel) -> DatasetResponse:
    return DatasetResponse(
        id=model.id,
        name=model.name,
        filename=model.filename,
        size_bytes=model.size_bytes,
        sha256=model.sha256,
        row_count=model.row_count,
        column_count=model.column_count,
        role=DatasetRole(model.role),
        schema_info=DatasetSchemaInfo.model_validate(model.schema_json),
        created_at=model.created_at,
    )


@router.post(
    "/upload",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Dataset CSV",
    description="Upload a CSV dataset with role 'reference' or 'incoming'. Performs strict validation, streams to disk, computes schema and SHA-256.",
    dependencies=[Depends(require_api_key)],
)
def upload_dataset(
    file: UploadFile = File(..., description="CSV file to upload"),
    role: DatasetRole = Form(DatasetRole.REFERENCE, description="Role of dataset: reference or incoming"),
    db: Session = Depends(get_db),
) -> DatasetResponse:
    if not file.filename:
        raise ValidationAppError("Missing filename in uploaded file.")

    dataset = save_dataset(
        db=db,
        file_stream=file.file,
        original_filename=file.filename,
        role=role,
    )
    return model_to_response(dataset)


@router.get(
    "",
    response_model=PaginatedResponse[DatasetResponse],
    summary="List Datasets",
    description="List uploaded datasets with pagination and optional role filtering.",
    dependencies=[Depends(require_api_key)],
)
def list_datasets(
    role: Optional[DatasetRole] = Query(None, description="Filter by dataset role"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DatasetResponse]:
    query = db.query(DatasetModel)
    if role:
        query = query.filter(DatasetModel.role == role.value)

    total = query.count()
    records = query.order_by(DatasetModel.created_at.desc()).offset(offset).limit(limit).all()
    items = [model_to_response(r) for r in records]

    return PaginatedResponse[DatasetResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetResponse,
    summary="Get Dataset Details",
    description="Retrieve metadata and inferred schema for a specific dataset ID.",
    dependencies=[Depends(require_api_key)],
)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
) -> DatasetResponse:
    dataset = get_dataset_by_id(db, dataset_id)
    return model_to_response(dataset)


@router.post(
    "/{reference_id}/validate-incoming/{incoming_id}",
    response_model=ValidationResultResponse,
    summary="Validate Incoming Against Reference Schema",
    description="Check missing columns, unexpected columns, incompatible dtypes, and compute data-quality summary.",
    dependencies=[Depends(require_api_key)],
)
def validate_incoming_dataset(
    reference_id: str,
    incoming_id: str,
    target_column: Optional[str] = Query(None, description="Optional target label column name"),
    db: Session = Depends(get_db),
) -> ValidationResultResponse:
    ref_dataset = get_dataset_by_id(db, reference_id)
    inc_dataset = get_dataset_by_id(db, incoming_id)

    ref_schema = DatasetSchemaInfo.model_validate(ref_dataset.schema_json)
    inc_df = load_dataset_dataframe(inc_dataset)

    is_valid, issues, quality = validate_incoming_against_reference(
        ref_schema=ref_schema,
        incoming_df=inc_df,
        target_column=target_column,
    )

    return ValidationResultResponse(
        is_valid=is_valid,
        issues=issues,
        quality_summary=quality,
        reference_dataset_id=reference_id,
        incoming_dataset_id=incoming_id,
    )
