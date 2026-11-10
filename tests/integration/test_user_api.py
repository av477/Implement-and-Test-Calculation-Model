"""HTTP API tests: FastAPI + Pydantic validation + real PostgreSQL."""

import pytest

pytestmark = pytest.mark.integration

PAYLOAD = {"username": "erin", "email": "erin@example.com", "password": "Secret123"}


def register(client, **overrides):
    return client.post("/users", json={**PAYLOAD, **overrides})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_returns_user_without_password(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "erin"
    assert body["email"] == "erin@example.com"
    assert "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username_returns_409(client):
    assert register(client).status_code == 201

    response = register(client, email="another@example.com")
    assert response.status_code == 409


def test_register_duplicate_email_is_case_insensitive(client):
    assert register(client).status_code == 201

    response = register(client, username="erin2", email="ERIN@Example.com")
    assert response.status_code == 409


def test_register_invalid_email_returns_422(client):
    response = register(client, email="not-an-email")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_register_weak_password_returns_422(client):
    response = register(client, password="weakpass")
    assert response.status_code == 422


def test_get_user_by_id(client):
    user_id = register(client).json()["id"]

    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "erin"
    assert "password_hash" not in response.json()


def test_get_missing_user_returns_404(client):
    assert client.get("/users/999999").status_code == 404


def test_verify_credentials(client):
    register(client)

    ok = client.post("/users/verify", json={"username": "erin", "password": "Secret123"})
    bad = client.post("/users/verify", json={"username": "erin", "password": "Wrong1234"})
    assert ok.status_code == 200
    assert bad.status_code == 401
