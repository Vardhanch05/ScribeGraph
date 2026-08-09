import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from quantinsight.api.main import create_app

class DummyValidationModel(BaseModel):
    name: str
    age: int

@pytest.fixture
def client():
    app = create_app()

    # Add dummy test routes to trigger validation / generic errors
    router = APIRouter()

    @router.post("/test-validation")
    def test_validation(data: DummyValidationModel):
        return {"status": "ok"}

    @router.get("/test-generic-error")
    def test_generic_error():
        raise RuntimeError("Something went wrong internally.")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "ScribeGraph Core API"

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_404_not_found(client):
    response = client.get("/non-existent-route-path")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "details" in data["error"]

def test_validation_error(client):
    # Invalid model payload (age is not an int, name is missing)
    response = client.post("/test-validation", json={"age": "not-a-number"})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"
    assert "errors" in data["error"]["details"]

def test_generic_error(client):
    response = client.get("/test-generic-error")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["details"]["error_class"] == "RuntimeError"
