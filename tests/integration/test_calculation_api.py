"""HTTP API tests for /calculate and /calculations."""

import uuid

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def user_id(client):
    response = client.post(
        "/users",
        json={"username": "calc_api", "email": "calc_api@example.com", "password": "Secret123"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create(client, owner_id, **payload):
    return client.post(
        "/calculations", json={"a": 8, "b": 2, "type": "Divide", "user_id": owner_id, **payload}
    )


def test_calculator_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<h1>Calculator</h1>" in response.text


@pytest.mark.parametrize(
    ("calculation_type", "expected"),
    [("Add", 10), ("Sub", 6), ("Multiply", 16), ("Divide", 4), ("divide", 4)],
)
def test_calculate_without_saving(client, calculation_type, expected):
    response = client.post("/calculate", json={"a": 8, "b": 2, "type": calculation_type})

    assert response.status_code == 200
    assert response.json() == {
        "a": 8,
        "b": 2,
        "type": calculation_type.capitalize(),
        "result": expected,
    }
    assert client.get("/calculations").json() == []


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"a": 1, "b": 0, "type": "Divide"}, "b must not be zero"),
        ({"a": 1e308, "b": 10, "type": "Multiply"}, "too large"),
        ({"a": 1, "b": 2, "type": "Power"}, "Input should be"),
    ],
)
def test_calculate_errors_return_422(client, payload, message):
    response = client.post("/calculate", json=payload)
    assert response.status_code == 422
    assert message in response.text


@pytest.mark.parametrize(
    ("calculation_type", "expected"),
    [("Add", 10), ("Sub", 6), ("Multiply", 16), ("Divide", 4), ("divide", 4)],
)
def test_create_calculation(client, user_id, calculation_type, expected):
    response = create(client, user_id, type=calculation_type)

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == calculation_type.capitalize()
    assert body["result"] == expected
    assert body["user_id"] == user_id
    assert str(uuid.UUID(body["id"])) == body["id"]
    assert body["created_at"] and body["updated_at"]


def test_divide_by_zero_returns_422(client, user_id):
    response = create(client, user_id, b=0)
    assert response.status_code == 422
    assert "b must not be zero" in response.text


@pytest.mark.parametrize(
    "payload",
    [{"type": "Power"}, {"a": "abc"}, {"b": None}, {"user_id": None}, {"user_id": "123"}],
)
def test_invalid_input_returns_422(client, user_id, payload):
    assert create(client, user_id, **payload).status_code == 422


def test_result_too_large_returns_422(client, user_id):
    response = create(client, user_id, a=1e308, b=10, type="Multiply")
    assert response.status_code == 422
    assert response.json()["detail"] == "Result is too large to store"


def test_unknown_user_returns_404(client):
    assert create(client, str(uuid.uuid4())).status_code == 404


def test_get_and_list_calculations(client, user_id):
    mine = create(client, user_id).json()

    assert client.get(f"/calculations/{mine['id']}").json() == mine
    assert client.get("/calculations").json() == [mine]
    assert client.get(f"/calculations?user_id={user_id}").json() == [mine]
    assert client.get(f"/calculations?user_id={uuid.uuid4()}").json() == []


def test_get_missing_calculation_returns_404(client):
    assert client.get(f"/calculations/{uuid.uuid4()}").status_code == 404


def test_get_with_malformed_id_returns_422(client):
    assert client.get("/calculations/42").status_code == 422


def test_patch_recomputes_result(client, user_id):
    calc = create(client, user_id).json()

    response = client.patch(f"/calculations/{calc['id']}", json={"a": 20})

    assert response.status_code == 200
    body = response.json()
    assert (body["a"], body["b"], body["type"], body["result"]) == (20, 2, "Divide", 10)
    assert body["created_at"] == calc["created_at"]


def test_patch_divide_by_zero_returns_422(client, user_id):
    calc = create(client, user_id).json()

    response = client.patch(f"/calculations/{calc['id']}", json={"b": 0})

    assert response.status_code == 422
    assert client.get(f"/calculations/{calc['id']}").json()["result"] == 4


def test_patch_needs_a_value(client, user_id):
    calc = create(client, user_id).json()
    assert client.patch(f"/calculations/{calc['id']}", json={}).status_code == 422


def test_patch_missing_calculation_returns_404(client):
    assert client.patch(f"/calculations/{uuid.uuid4()}", json={"a": 1}).status_code == 404
