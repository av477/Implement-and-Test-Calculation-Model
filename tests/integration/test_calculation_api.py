"""HTTP API tests for /calculations."""

import pytest

pytestmark = pytest.mark.integration


def create(client, **payload):
    return client.post("/calculations", json={"a": 8, "b": 2, "type": "Divide", **payload})


def register_user(client):
    response = client.post(
        "/users",
        json={"username": "calc_api", "email": "calc_api@example.com", "password": "Secret123"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize(
    ("calculation_type", "expected"),
    [("Add", 10), ("Sub", 6), ("Multiply", 16), ("Divide", 4), ("divide", 4)],
)
def test_create_calculation(client, calculation_type, expected):
    response = create(client, type=calculation_type)

    assert response.status_code == 201
    body = response.json()
    assert body["a"] == 8
    assert body["b"] == 2
    assert body["type"] == calculation_type.capitalize()
    assert body["result"] == expected
    assert body["user_id"] is None
    assert "id" in body and "created_at" in body


def test_divide_by_zero_returns_422(client):
    response = create(client, b=0)
    assert response.status_code == 422
    assert "b must not be zero" in response.text


@pytest.mark.parametrize(
    "payload",
    [{"type": "Power"}, {"a": "abc"}, {"b": None}, {"user_id": 0}],
)
def test_invalid_input_returns_422(client, payload):
    assert create(client, **payload).status_code == 422


def test_result_too_large_returns_422(client):
    response = create(client, a=1e308, b=10, type="Multiply")
    assert response.status_code == 422
    assert response.json()["detail"] == "Result is too large to store"


def test_unknown_user_returns_404(client):
    response = create(client, user_id=999999)
    assert response.status_code == 404


def test_calculation_for_user_and_listing(client):
    user_id = register_user(client)
    mine = create(client, user_id=user_id).json()
    other = create(client, type="Add").json()

    assert client.get(f"/calculations/{mine['id']}").json() == mine
    assert [c["id"] for c in client.get("/calculations").json()] == [mine["id"], other["id"]]
    assert [c["id"] for c in client.get(f"/calculations?user_id={user_id}").json()] == [mine["id"]]


def test_get_missing_calculation_returns_404(client):
    assert client.get("/calculations/999999").status_code == 404
