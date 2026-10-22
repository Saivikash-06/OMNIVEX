import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.core.errors import SecurityViolationError
from backend.app.database.models import TrainedModel
from backend.app.services.model_service import load_model_pipeline


@pytest.fixture
def uploaded_training_dataset(client: TestClient) -> str:
    # 100 rows classification dataset
    header = "f1,f2,cat_col,label\n"
    rows = []
    for i in range(100):
        c = "A" if i % 2 == 0 else "B"
        lbl = 1 if i % 3 == 0 else 0
        rows.append(f"{i * 1.5},{i * 0.5},{c},{lbl}")
    csv_content = header + "\n".join(rows)

    resp = client.post(
        "/api/datasets/upload",
        files={"file": ("train_data.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_train_model_valid(client: TestClient, uploaded_training_dataset: str):
    req_body = {
        "name": "Test Classifier",
        "dataset_id": uploaded_training_dataset,
        "target_column": "label",
        "algorithm": "logistic_regression",
        "hyperparameters": {"C": 2.0, "max_iter": 300},
        "test_size": 0.25,
        "random_seed": 42,
    }
    resp = client.post("/api/models/train", json=req_body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Classifier"
    assert data["algorithm"] == "logistic_regression"
    assert "accuracy" in data["baseline_metrics"]
    assert data["baseline_metrics"]["sample_size"] == 25  # 25% of 100
    assert len(data["artifact_sha256"]) == 64


def test_target_leakage_rejection(client: TestClient, uploaded_training_dataset: str):
    req_body = {
        "name": "Leaky Classifier",
        "dataset_id": uploaded_training_dataset,
        "target_column": "label",
        "feature_columns": ["f1", "f2", "label"],  # Target leaked!
        "algorithm": "logistic_regression",
    }
    resp = client.post("/api/models/train", json=req_body)
    assert resp.status_code == 422
    assert "leakage" in resp.json()["error"]["message"].lower()


def test_invalid_hyperparameters(client: TestClient, uploaded_training_dataset: str):
    # C out of bounds (> 100)
    req_body = {
        "name": "Bad Params",
        "dataset_id": uploaded_training_dataset,
        "target_column": "label",
        "algorithm": "logistic_regression",
        "hyperparameters": {"C": 9999.0},
    }
    resp = client.post("/api/models/train", json=req_body)
    assert resp.status_code == 422


def test_tampered_model_artifact_fails_integrity(client: TestClient, uploaded_training_dataset: str, test_app, temp_dirs):
    req_body = {
        "name": "Integrity Test Model",
        "dataset_id": uploaded_training_dataset,
        "target_column": "label",
        "algorithm": "random_forest",
        "hyperparameters": {"n_estimators": 20},
    }
    resp = client.post("/api/models/train", json=req_body)
    assert resp.status_code == 201
    model_data = resp.json()
    model_id = model_data["id"]
    artifact_filename = model_data["artifact_filename"]

    # Tamper with the artifact file directly on disk
    artifact_path = temp_dirs["models"] / artifact_filename
    assert artifact_path.exists()
    with open(artifact_path, "ab") as f:
        f.write(b"\n#MALICIOUS_TAMPERED_BYTE_APPENDED")

    # Now attempt to predict with this model - it must fail hash verification
    pred_resp = client.post(
        f"/api/models/{model_id}/predict",
        json={"dataset_id": uploaded_training_dataset},
    )
    assert pred_resp.status_code == 400
    assert "integrity check failed" in pred_resp.json()["error"]["message"].lower()


def test_prediction_compatible_and_incompatible_features(client: TestClient, uploaded_training_dataset: str):
    # Train model
    req_body = {
        "name": "Pred Test",
        "dataset_id": uploaded_training_dataset,
        "target_column": "label",
        "algorithm": "decision_tree",
    }
    train_resp = client.post("/api/models/train", json=req_body)
    model_id = train_resp.json()["id"]

    # Predict on compatible dataset
    pred_resp = client.post(
        f"/api/models/{model_id}/predict",
        json={"dataset_id": uploaded_training_dataset},
    )
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()
    assert pred_data["sample_count"] == 100
    assert len(pred_data["predictions"]) == 100

    # Incompatible dataset (missing f1, f2)
    bad_csv = "cat_col,other_col\nA,1\nB,2\n"
    bad_resp = client.post(
        "/api/datasets/upload",
        files={"file": ("bad_features.csv", io.BytesIO(bad_csv.encode("utf-8")), "text/csv")},
        data={"role": "incoming"},
    )
    bad_id = bad_resp.json()["id"]

    fail_pred = client.post(
        f"/api/models/{model_id}/predict",
        json={"dataset_id": bad_id},
    )
    assert fail_pred.status_code == 422
    assert "missing required feature" in fail_pred.json()["error"]["message"].lower()
