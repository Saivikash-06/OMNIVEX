import io
import pytest
import numpy as np
from fastapi.testclient import TestClient
import pandas as pd
from backend.app.schemas.common import DatasetRole
from backend.app.services.dataset_service import (
    build_preprocessor_pipeline,
    classify_dtype,
    validate_incoming_against_reference,
    infer_dataset_schema,
)


def test_valid_csv_upload(client: TestClient):
    csv_content = "age,salary,department,churn\n25,50000,sales,0\n30,60000,engineering,1\n35,75000,marketing,0\n"
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("test_ref.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test_ref.csv"
    assert data["role"] == "reference"
    assert data["row_count"] == 3
    assert data["column_count"] == 4
    assert len(data["sha256"]) == 64
    assert len(data["schema_info"]["columns"]) == 4


def test_invalid_extension_upload(client: TestClient):
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("test.txt", io.BytesIO(b"some,data\n1,2\n"), "text/plain")},
        data={"role": "reference"},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_empty_file_upload(client: TestClient):
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        data={"role": "reference"},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_binary_nul_byte_upload(client: TestClient):
    content = b"col1,col2\n1,2\n\x00\x01\x02binary\n"
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("binary.csv", io.BytesIO(content), "text/csv")},
        data={"role": "reference"},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_duplicate_columns_upload(client: TestClient):
    content = "col1,col1,col2\n1,2,3\n"
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("duplicate.csv", io.BytesIO(content.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    assert response.status_code == 422
    data = response.json()
    assert "Duplicate column" in data["error"]["message"]


def test_path_traversal_filename_sanitized(client: TestClient):
    content = "col1,col2\n10,20\n30,40\n"
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("../../etc/passwd.csv", io.BytesIO(content.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    assert response.status_code == 201
    data = response.json()
    # The filename stored should be a server UUID and display name sanitized
    assert ".." not in data["filename"]
    assert "/" not in data["filename"]
    assert "\\" not in data["filename"]


def test_dataset_listing_and_pagination(client: TestClient):
    for i in range(3):
        csv_data = f"feat1,feat2\n{i},{i+1}\n"
        client.post(
            "/api/datasets/upload",
            files={"file": (f"ref_{i}.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
            data={"role": "reference"},
        )

    response = client.get("/api/datasets?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 3
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_schema_validation_incoming_against_reference(client: TestClient):
    ref_csv = "age,salary,city,churn\n25,50000,ny,0\n30,60000,sf,1\n35,70000,ny,0\n40,80000,sf,1\n"
    ref_res = client.post(
        "/api/datasets/upload",
        files={"file": ("ref_val.csv", io.BytesIO(ref_csv.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    ref_id = ref_res.json()["id"]

    # Incoming with missing 'city', unexpected 'country', incompatible 'salary' (text), excessive nulls in 'age'
    inc_csv = "age,salary,country,churn\n,not_a_number,usa,0\n,also_text,usa,1\n,bad_num,canada,0\n20,bad_num,usa,1\n"
    inc_res = client.post(
        "/api/datasets/upload",
        files={"file": ("inc_val.csv", io.BytesIO(inc_csv.encode("utf-8")), "text/csv")},
        data={"role": "incoming"},
    )
    inc_id = inc_res.json()["id"]

    val_res = client.post(f"/api/datasets/{ref_id}/validate-incoming/{inc_id}?target_column=churn")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["is_valid"] is False
    categories = [i["category"] for i in val_data["issues"]]
    assert "missing_columns" in categories
    assert "unexpected_columns" in categories
    assert "incompatible_dtypes" in categories
    assert "excessive_nulls" in categories
    assert val_data["quality_summary"] is not None


def test_preprocessing_pipeline_fit_reference_only():
    ref_df = pd.DataFrame({
        "num1": [10.0, 20.0, np.nan, 40.0],
        "cat1": ["A", "B", "A", None],
    })
    inc_df = pd.DataFrame({
        "num1": [np.nan, 100.0],
        "cat1": ["C", "B"],  # C is unseen category
    })

    preprocessor, num_cols, cat_cols = build_preprocessor_pipeline(ref_df, ["num1", "cat1"])
    # Transform incoming without error, unseen categories encoded as zeros
    transformed = preprocessor.transform(inc_df[["num1", "cat1"]])
    assert transformed.shape[0] == 2
    # Verify no NaNs remained after reference-fitted pipeline
    assert not np.isnan(transformed).any()
