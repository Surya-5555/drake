import pytest
from fastapi.testclient import TestClient
from src.proxy.api import app
import os

client = TestClient(app)


def test_api_security_missing_key():
    response = client.post("/api/v1/workflows/fake-id/approve")
    assert response.status_code == 403
    assert "Could not validate API key" in response.json()["detail"]


def test_api_security_invalid_key():
    response = client.post(
        "/api/v1/workflows/fake-id/reject", headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 403


def test_api_security_valid_key():
    # Will fail 404 because fake-id doesn't exist, but passes auth
    valid_key = os.getenv("DELL_MCP_API_KEY", "default_dev_key")
    response = client.post(
        "/api/v1/workflows/fake-id/approve", headers={"X-API-Key": valid_key}
    )
    assert response.status_code == 404
