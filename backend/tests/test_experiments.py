import io
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def experiment_datasets(client: TestClient):
    ref_rows = ["age,income,churn"] + [f"{20+i},{30000+i*500},{i%2}" for i in range(60)]
    inc_rows = ["age,income,churn"] + [f"{20+i},{30000+i*500},{i%2}" for i in range(60)]

    ref_resp = client.post(
        "/api/datasets/upload",
        files={"file": ("exp_ref.csv", io.BytesIO("\n".join(ref_rows).encode("utf-8")), "text/csv")},
        data={"role": "reference"},
    )
    inc_resp = client.post(
        "/api/datasets/upload",
        files={"file": ("exp_inc.csv", io.BytesIO("\n".join(inc_rows).encode("utf-8")), "text/csv")},
        data={"role": "incoming"},
    )

    # Train a baseline model
    model_resp = client.post(
        "/api/models/train",
        json={
            "name": "Exp Model",
            "dataset_id": ref_resp.json()["id"],
            "target_column": "churn",
            "algorithm": "logistic_regression",
            "random_seed": 42,
        },
    )

    return {
        "ref_id": ref_resp.json()["id"],
        "inc_id": inc_resp.json()["id"],
        "model_id": model_resp.json()["id"],
    }


def test_experiment_repeatability_with_same_seed(client: TestClient, experiment_datasets):
    """Repeatability test: running the same experiment settings with the same seed and data

    must produce identical numeric results.
    """
    req_body = {
        "name": "Repeatability Trial",
        "scenario": "baseline",
        "reference_dataset_id": experiment_datasets["ref_id"],
        "incoming_dataset_id": experiment_datasets["inc_id"],
        "model_id": experiment_datasets["model_id"],
        "random_seed": 42,
        "ks_alpha": 0.05,
    }

    run1 = client.post("/api/experiments", json=req_body)
    assert run1.status_code == 201
    data1 = run1.json()

    run2 = client.post("/api/experiments", json=req_body)
    assert run2.status_code == 201
    data2 = run2.json()

    # Verify identical drift statistics
    drift1 = {f["feature"]: f["statistic"] for f in data1["drift_results"]["per_feature_results"]}
    drift2 = {f["feature"]: f["statistic"] for f in data2["drift_results"]["per_feature_results"]}
    assert drift1 == drift2

    # Verify identical performance metrics
    assert data1["performance_metrics"]["accuracy"] == data2["performance_metrics"]["accuracy"]
    assert data1["performance_metrics"]["f1"] == data2["performance_metrics"]["f1"]
    assert data1["reliability"]["reliability_state"] == data2["reliability"]["reliability_state"]


def test_experiment_simulation_labelling(client: TestClient, experiment_datasets):
    req_body = {
        "name": "=cmd|' /C calc'!A0",  # Test formula injection in name
        "scenario": "drift_simulation",
        "reference_dataset_id": experiment_datasets["ref_id"],
        "incoming_dataset_id": experiment_datasets["inc_id"],
        "model_id": experiment_datasets["model_id"],
        "simulation": {
            "simulation_type": "mean_shift",
            "magnitude": 3.0,
            "target_features": ["income"],
            "seed": 99,
        },
    }
    resp = client.post("/api/experiments", json=req_body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_simulation"] is True
    assert data["simulation_parameters"]["simulation_type"] == "mean_shift"
    exp_id = data["experiment_id"]

    # Test CSV export and formula injection neutralization
    csv_resp = client.get(f"/api/experiments/{exp_id}/export?format=csv")
    assert csv_resp.status_code == 200
    csv_text = csv_resp.text
    assert "[SIMULATED]" in csv_text
    # Cell starting with '=' should be prepended with "'"
    assert "'=cmd|' /C calc'!A0" in csv_text

    # Test JSON export
    json_resp = client.get(f"/api/experiments/{exp_id}/export?format=json")
    assert json_resp.status_code == 200
    json_data = json_resp.json()
    assert json_data["tag"] == "SIMULATED"
    assert json_data["schema_version"] == "2.0.0"
    assert "experiment" in json_data
    assert "monitoring_run" in json_data


def test_list_and_get_experiment(client: TestClient, experiment_datasets):
    list_resp = client.get("/api/experiments?limit=10&offset=0")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1
    first_id = data["items"][0]["id"]

    get_resp = client.get(f"/api/experiments/{first_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["experiment"]["id"] == first_id
