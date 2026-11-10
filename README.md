# Implement and Test a Calculation Model

A FastAPI service that builds on the Assignment 10 secure user model and adds a
**calculation model**: a SQLAlchemy `Calculation` table, Pydantic schemas with
validation, and a **Factory pattern** that picks the right math operation (Add,
Sub, Multiply, Divide). It has unit and integration tests and a GitHub Actions
pipeline that pushes a Docker image to Docker Hub when the tests pass.

**Docker Hub repository:** [av477/calculation-model](https://hub.docker.com/r/av477/calculation-model)

## Features

| Requirement | Where |
|---|---|
| SQLAlchemy `Calculation` model: `id`, `a`, `b`, `type`, `result`, `user_id` (foreign key to `users.id`), `created_at` | [`app/models/calculation.py`](app/models/calculation.py) |
| `CalculationCreate` (a, b, type, optional user_id) and `CalculationRead` | [`app/schemas/calculation.py`](app/schemas/calculation.py) |
| Factory: `CalculationFactory.create(type)` returns an `AddOperation`, `SubOperation`, `MultiplyOperation` or `DivideOperation` | [`app/calculations/factory.py`](app/calculations/factory.py) |
| Create, get and list calculations | [`app/operations/calculations.py`](app/operations/calculations.py) |
| SQLAlchemy `User` model, schemas and bcrypt hashing (from Assignment 10) | [`app/models/user.py`](app/models/user.py), [`app/schemas/user.py`](app/schemas/user.py), [`app/auth/security.py`](app/auth/security.py) |
| REST API | [`app/main.py`](app/main.py) |
| Unit tests (no database) | [`tests/unit/`](tests/unit) |
| Integration tests (real PostgreSQL) | [`tests/integration/`](tests/integration) |
| CI/CD (test, scan, then push to Docker Hub) | [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) |

### Design choices

- **The result is stored, not computed on demand.** It is calculated once, when
  the calculation is created, and saved in the `result` column. The inputs never
  change, so the stored result can't go out of date, and reading or listing
  calculations doesn't redo any math.
- **`user_id` is an optional, real foreign key.** A calculation can belong to a
  user or to nobody. PostgreSQL rejects a `user_id` that doesn't exist, the API
  returns **404** for it, and deleting a user also deletes their calculations
  (`ON DELETE CASCADE`).
- **`type` is an enumeration** (`Add`, `Sub`, `Multiply`, `Divide`). The API
  accepts any letter case (`add`, `ADD`) and always returns the standard
  spelling. The database also has a `CHECK` constraint, so no other value can
  be stored even by raw SQL.
- **Validation:**
  - Divide with `b = 0` is rejected with **422** before anything is saved.
  - `a` and `b` must be real numbers, so text, `inf` and `nan` are rejected.
  - A result too large to store (for example `1e308 × 10`) is also rejected with **422**.

### How the factory works

Each operation is a small class with a `compute(a, b)` method. The factory keeps
a table that maps each `CalculationType` to its class:

```python
operation = CalculationFactory.create(CalculationType.DIVIDE)  # a DivideOperation
operation.compute(10, 4)                                       # 2.5
```

The rest of the app never needs an `if type == "Add" ... elif ...` chain. To add
a new operation such as `Power`, you write one new class and add one line to the
factory's table.

## API

| Method | Path | Description | Responses |
|---|---|---|---|
| `GET` | `/health` | Health check | 200 |
| `POST` | `/calculations` | Create a calculation (`CalculationCreate`) | 201, 404 unknown user, 422 invalid input |
| `GET` | `/calculations` | List calculations, optionally `?user_id=` | 200 |
| `GET` | `/calculations/{id}` | Get a calculation (`CalculationRead`) | 200, 404 |
| `POST` | `/users` | Register a user (`UserCreate`) | 201, 409 duplicate, 422 invalid input |
| `GET` | `/users/{id}` | Get a user (`UserRead`) | 200, 404 |
| `POST` | `/users/verify` | Check a username/email and password | 200, 401 |

Example request and response:

```bash
curl -X POST http://localhost:8000/calculations -H "Content-Type: application/json" -d '{"a": 10, "b": 4, "type": "Divide"}'
```

```json
{"id": 1, "a": 10.0, "b": 4.0, "type": "Divide", "result": 2.5, "user_id": null, "created_at": "2026-11-10T12:00:00Z"}
```

Interactive docs: `http://localhost:8000/docs`

## Run with Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL 17 and the API on `http://localhost:8000`. If ports 5432 or 8000 are already in use, choose others:

```bash
DB_PORT=5434 API_PORT=8001 docker compose up --build
```

## Run the Docker Hub image

You can run the published image without cloning the repository. The API needs a
PostgreSQL database, and you give it the address in the `DATABASE_URL`
environment variable. If you start the image on its own with
`docker run av477/calculation-model`, the app looks for PostgreSQL at
`localhost:5432`. Inside a container, `localhost` is the container itself, so
startup fails with `Connection refused`.

1. Create a network so the two containers can reach each other by name:

   ```bash
   docker network create calc-net
   ```

2. Start PostgreSQL on that network:

   ```bash
   docker run -d --name calc-db --network calc-net -e POSTGRES_USER=appuser -e POSTGRES_PASSWORD=apppassword -e POSTGRES_DB=secure_users postgres:17
   ```

3. Wait until PostgreSQL is ready. Repeat this command until it reports `accepting connections`:

   ```bash
   docker exec calc-db pg_isready -U appuser -d secure_users
   ```

4. Start the API on the same network, pointing it at the database container by its name:

   ```bash
   docker run --rm --name calc-api -p 8000:8000 --network calc-net -e DATABASE_URL=postgresql+psycopg2://appuser:apppassword@calc-db:5432/secure_users av477/calculation-model:latest
   ```

5. Open `http://localhost:8000/docs` to try the API. The tables are created automatically on startup.

To use a specific build instead of `latest`, replace the tag with a commit SHA
from the [Docker Hub tags page](https://hub.docker.com/r/av477/calculation-model/tags).
If port 8000 is already in use, change the first port, for example `-p 8001:8000`.

To stop and clean up (press `Ctrl+C` in the API's terminal first):

```bash
docker rm -f calc-db
```

```bash
docker network rm calc-net
```

## Run the tests locally

Run the unit tests with `pytest tests/unit` (no database required). Integration
tests use a disposable PostgreSQL database; set `DATABASE_URL` to that test
database before running them. The integration tests drop and recreate the
`users` and `calculations` tables, so do not point them at production or other
data you need.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Unit tests need no database
pytest tests/unit --cov=app

# Integration tests need a disposable PostgreSQL database
docker run --rm -d --name test-db -e POSTGRES_USER=ci_user -e POSTGRES_PASSWORD=ci_password \
  -e POSTGRES_DB=ci_users -p 5433:5432 postgres:17
export DATABASE_URL=postgresql+psycopg2://ci_user:ci_password@localhost:5433/ci_users
pytest tests/integration --cov=app --cov-append --cov-report=term-missing
```

In Windows PowerShell, set the database URL with
`$env:DATABASE_URL = "postgresql+psycopg2://ci_user:ci_password@localhost:5433/ci_users"` instead of `export`.
Before running the integration tests, check that PostgreSQL is ready with
`docker exec test-db pg_isready -U ci_user -d ci_users`; repeat until it reports
that the server is accepting connections. Stop the disposable database with
`docker stop test-db` after the tests finish.

Each integration test runs inside a transaction that is rolled back afterwards, so tests don't affect one another.

**What is tested**
- *Unit (calculations):*
  - The factory returns the right class for each type and rejects unknown types.
  - Add, Sub, Multiply and Divide give the right answers, including negatives and decimals.
  - Dividing by zero and results that are too large are rejected.
  - `CalculationCreate` accepts types in any letter case and rejects unknown types, a zero divisor, missing fields, non-numbers, `inf`/`nan` and bad user IDs.
- *Unit (users):* bcrypt hashing and verification; validation of usernames, emails and password strength; `UserRead` never exposes the hash.
- *Integration (calculations):*
  - The computed result is stored in PostgreSQL, and every type is saved and loaded back correctly.
  - The foreign key rejects a missing user, and the `CHECK` constraint rejects an unknown type.
  - Deleting a user deletes their calculations, and listing can be filtered by user.
  - The API returns 201, 404 and 422 as expected.
- *Integration (users):* the hash (not the password) is stored; duplicate usernames and emails are rejected; the API returns 201, 409, 422, 404 and 401 as expected.

## CI/CD

On every push to any branch, and on pull requests to `main`, GitHub Actions:
1. **Test:** starts a PostgreSQL 17 service container, installs dependencies, and runs the unit tests and then the integration tests with combined coverage. The workflow fails unless total coverage is at least 90%.
2. **Build and scan:** builds the Docker image and scans it for fixable high and critical OS or library vulnerabilities. A failed scan blocks publishing.
3. **Deploy** (pushes to `main` only, after tests and a successful scan): logs in to Docker Hub and pushes the scanned image as `calculation-model:latest` and `calculation-model:<commit-sha>`. Pull requests run the build and scan but never log in or publish.

### Setup
1. On Docker Hub, create an access token (**Account settings → Personal access tokens**, with *Read & Write* access).
2. In the GitHub repository, go to **Settings → Secrets and variables → Actions** and add:
   - `DOCKERHUB_USERNAME`: your Docker Hub username
   - `DOCKERHUB_TOKEN`: the access token
3. Push to `main` and watch the **Actions** tab.

Pull the published image:

```bash
docker pull av477/calculation-model:latest
```

See [Run the Docker Hub image](#run-the-docker-hub-image) for how to run it with a database.

## Project structure

```
app/
  auth/
    security.py      bcrypt hash_password / verify_password
  calculations/
    factory.py       CalculationType, operation classes, CalculationFactory
  models/
    calculation.py   SQLAlchemy Calculation model
    user.py          SQLAlchemy User model
  operations/
    calculations.py  create / get / list calculations
    users.py         create / get / authenticate users
  schemas/
    calculation.py   Pydantic CalculationCreate / CalculationRead
    user.py          Pydantic UserCreate / UserRead / UserLogin
  config.py          settings from environment variables
  database.py        engine, session factory, declarative Base
  main.py            FastAPI routes
tests/
  unit/              factory, schema and hashing tests
  integration/       PostgreSQL model and API tests
.github/workflows/ci-cd.yml
Dockerfile
docker-compose.yml
```
