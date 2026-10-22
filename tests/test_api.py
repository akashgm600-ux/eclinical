"""Integration tests for FastAPI REST API endpoints."""

from fastapi.testclient import TestClient


def test_health_endpoint(test_client: TestClient):
    """Verify health endpoint returns status 200."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "pipeline_version" in data


def test_list_runs_endpoint(test_client: TestClient):
    """Verify listing pipeline runs."""
    response = test_client.get("/api/v1/runs?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_metrics_summary_endpoint(test_client: TestClient):
    """Verify quality summary metrics aggregation."""
    response = test_client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_runs" in data
    assert "overall_pass_rate_pct" in data
    assert "most_frequent_quarantine_rules" in data


def test_quarantine_endpoint_with_filters(test_client: TestClient):
    """Verify quarantine retrieval and query parameters."""
    response = test_client.get("/api/v1/quarantine?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        record = data[0]
        assert "rule_code" in record
        assert "source_entity" in record
        assert "error_message" in record
