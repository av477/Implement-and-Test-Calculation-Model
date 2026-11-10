# Implement and Test a Calculation Model

A FastAPI service that builds on the Assignment 10 secure user model and adds a
**calculation model**:

- a **polymorphic** SQLAlchemy model (`Addition`, `Subtraction`,
  `Multiplication`, `Division`) in one `calculations` table;
- Pydantic schemas with validation;
- a **factory** (`Calculation.create()`) that picks the right subclass;
- a simple **calculator web page**.

It has unit, integration and Playwright browser tests, and a GitHub Actions
pipeline that pushes a Docker image to Docker Hub when the tests pass.

**Docker Hub repository:** [av477/calculation-model](https://hub.docker.com/r/av477/calculation-model)

## Features

| Requirement | Where |
|---|---|
| SQLAlchemy `Calculation` model: `id` (UUID), `user_id` (UUID foreign key to `users.id`, required), `type`, `a`, `b`, `result`, `created_at`, `updated_at` | [`app/models/calculation.py`](app/models/calculation.py) |
| Polymorphic subclasses `Addition`, `Subtraction`, `Multiplication`, `Division` (single-table inheritance, `type` is the discriminator) | [`app/models/calculation.py`](app/models/calculation.py) |
| Factory: `Calculation.create(type, a, b, user_id)` returns the right subclass with its result filled in | [`app/models/calculation.py`](app/models/calculation.py) |
| `CalculationCreate` (a, b, type, user_id), `CalculationRead`, `CalculationUpdate` | [`app/schemas/calculation.py`](app/schemas/calculation.py) |
| Create, get, list and update calculations | [`app/operations/calculations.py`](app/operations/calculations.py) |
| Calculator web page at `/` (Jinja2 template) | [`app/templates/index.html`](app/templates/index.html) |
| Alembic migrations (used by Docker Compose, the Docker image, CI and the tests) | [`alembic/`](alembic) |
| `CheckConstraint` (no `Divide` with `b = 0`), `@validates`, `hybrid_property` `expression`, composite index | [`app/models/calculation.py`](app/models/calculation.py) |
| `column_property` `calculation_count`, `selectinload` route | [`app/models/user.py`](app/models/user.py), [`app/operations/users.py`](app/operations/users.py) |
| SQLAlchemy `User` model (UUID id), schemas and bcrypt hashing (from Assignment 10) | [`app/models/user.py`](app/models/user.py), [`app/schemas/user.py`](app/schemas/user.py), [`app/auth/security.py`](app/auth/security.py) |
| REST API | [`app/main.py`](app/main.py) |
| Unit tests (no database) | [`tests/unit/`](tests/unit) |
| Integration tests (real PostgreSQL) | [`tests/integration/`](tests/integration) |
| End-to-end browser tests (Playwright + Chromium) | [`tests/e2e/`](tests/e2e) |
| CI/CD (test, scan, then push to Docker Hub) | [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) |

### Design choices

- **One table, four classes (polymorphism).** All calculations are stored in
  the `calculations` table. The `type` column (`Add`, `Sub`, `Multiply` or
  `Divide`) is the *discriminator*: when SQLAlchemy loads a row, it reads `type`
  and builds the matching subclass. So a row with `type = "Divide"` comes back
  as a `Division` object, and its `compute()` method does division. The
  database also has a `CHECK` constraint, so no other type can be stored.
- **The result is stored, not computed on demand.** It is worked out when the
  calculation is created, or when its numbers are changed, and saved in the
  `result` column. Reading or listing calculations never redoes the math.
- **UUID primary keys.** Users and calculations get random ids like
  `3f2b9c1e-...` instead of 1, 2, 3, so nobody can guess other ids or count the
  rows.
- **Every calculation belongs to a user.** `user_id` is required and is a real
  foreign key: PostgreSQL rejects a `user_id` that doesn't exist (the API
  returns **404**), and deleting a user also deletes their calculations
  (`ON DELETE CASCADE`).
- **`created_at` and `updated_at`.** Both are set when a row is created;
  `updated_at` changes whenever the calculation is updated.
- **Validation:**
  - `type` must be Add, Sub, Multiply or Divide, in any letter case (`add`,
    `ADD`). The API always returns the standard spelling.
  - Divide with `b = 0` is rejected with **422** before anything is saved.
  - `a` and `b` must be real numbers, so text, `inf` and `nan` are rejected.
  - A result too large to store (for example `1e308 × 10`) is also rejected
    with **422**.

### How the factory and the subclasses work

Each subclass only says how to do its own math:

```python
class Division(Calculation):
    __mapper_args__ = {"polymorphic_identity": "Divide"}

    def _apply(self, a, b):
        if b == 0:
            raise CalculationError("Cannot divide by zero")
        return a / b
```

`Calculation.create()` is the factory. It looks up the subclass registered for
a type, builds it and fills in the result:

```python
calc = Calculation.create("Divide", 10, 4, user_id)   # a Division object
calc.result                                           # 2.5
db.add(calc)
db.commit()

db.get(Calculation, calc.id)                          # comes back as a Division
```

The rest of the app never needs an `if type == "Add" ... elif ...` chain. To add
a new operation such as `Power`, you write one new subclass and add `Power` to
`CalculationType`.

### Calculator page

Open `http://localhost:8000/` to use the calculator. Enter two numbers, pick an
operation and press **Calculate**. The page sends the numbers to
`POST /calculate`, which uses the same factory and validation as the rest of the
API but doesn't save anything, so you don't need a user account. Errors such as
dividing by zero are shown in red.

## Advanced SQLAlchemy features

### Alembic migrations
A *migration* is a small Python script that creates or changes tables, saved
with the code. Alembic keeps a list of which ones have run (in the
`alembic_version` table), so `alembic upgrade head` only runs the new ones.
The first migration, [`alembic/versions/0001_...py`](alembic/versions), builds
the `users` and `calculations` tables with everything described above.

- The app no longer creates tables itself. Docker Compose runs a one-off
  `migrate` service (`alembic upgrade head`) before starting the API, and the
  Docker image runs the same command when it starts.
- When you change a model, create a new migration with
  `alembic revision --autogenerate -m "what changed"`, read it, then run
  `alembic upgrade head`.
- CI runs `alembic upgrade head` and `alembic check`. The check fails if the
  models and the migrations don't match, for example a new column without a
  migration.
- The tests build their database with the migrations too. A test also checks
  that the result matches the models exactly, and that downgrading and
  upgrading again works.

### CHECK constraint: no division by zero in the database
The table has the rule `NOT (type = 'Divide' AND b = 0)`. Pydantic already
blocks this in the API. The database rule is a safety net for anything that
skips the API, such as a script or raw SQL. A test inserts the row with raw SQL
and shows PostgreSQL refusing it.

### `@validates`: checking numbers on the model
`Calculation._validate_number` runs every time `a` or `b` is set on a
calculation object, even outside the API. It rejects anything that isn't a
real, finite number (text, `None`, `True`, `inf`, `nan`). It's a second layer
behind Pydantic.

### `hybrid_property`: `expression`
`calc.expression` gives the calculation as text, like `"6 + 3"`. "Hybrid" means
it works in two places:
- **on an object**, it is ordinary Python;
- **in a query**, it becomes SQL, so the database can filter or sort by it:

```python
select(Calculation).where(Calculation.expression == "6 + 3")
select(Calculation).order_by(Calculation.expression)
```

Tests check that the Python and SQL versions give the same text.

### Composite index on `(user_id, created_at)`
An index is like a book's index: it lets PostgreSQL jump to rows instead of
reading the whole table. This one is sorted by user and then by time. So "this
user's calculations, oldest first" reads the user's rows already in order. A
test checks that the index exists and that PostgreSQL uses it for that query.

### `selectinload`: loading a user with their calculations
`GET /users/{id}/calculations` returns a user with all their calculations. By
default SQLAlchemy loads `user.calculations` *lazily*, with an extra query the
first time you use it. With many users, that becomes one extra query per user
(the "N+1 problem"). `selectinload` loads them all at once with a second query
(`... WHERE user_id IN (...)`). A test counts the SQL statements: exactly two.

### `column_property`: `calculation_count`
`user.calculation_count` is the number of calculations a user has. It isn't a
stored column. It is a small subquery that PostgreSQL runs while loading the
user, so the count is always correct without loading the calculations. It also
works in queries, for example
`select(User).where(User.calculation_count > 0)`.

## API

| Method | Path | Description | Responses |
|---|---|---|---|
| `GET` | `/` | Calculator web page | 200 |
| `GET` | `/health` | Health check | 200 |
| `POST` | `/calculate` | Work out a result without saving it (`a`, `b`, `type`) | 200, 422 invalid input |
| `POST` | `/calculations` | Save a calculation for a user (`CalculationCreate`) | 201, 404 unknown user, 422 invalid input |
| `GET` | `/calculations` | List calculations, optionally `?user_id=` | 200 |
| `GET` | `/calculations/{id}` | Get a calculation (`CalculationRead`) | 200, 404, 422 malformed id |
| `PATCH` | `/calculations/{id}` | Change `a` and/or `b`; the result is recomputed (`CalculationUpdate`) | 200, 404, 422 invalid input |
| `POST` | `/users` | Register a user (`UserCreate`) | 201, 409 duplicate, 422 invalid input |
| `GET` | `/users/{id}` | Get a user (`UserRead`) | 200, 404, 422 malformed id |
| `GET` | `/users/{id}/calculations` | A user with `calculation_count` and all their calculations (`UserCalculations`) | 200, 404, 422 malformed id |
| `POST` | `/users/verify` | Check a username/email and password | 200, 401 |

Example: save a calculation (use the `id` returned by `POST /users` as `user_id`):

```bash
curl -X POST http://localhost:8000/calculations -H "Content-Type: application/json" -d '{"a": 10, "b": 4, "type": "Divide", "user_id": "<your user id>"}'
```

```json
{"id": "8c1d...", "user_id": "<your user id>", "type": "Divide", "a": 10.0, "b": 4.0, "result": 2.5, "created_at": "2026-11-10T12:00:00Z", "updated_at": "2026-11-10T12:00:00Z"}
```

Interactive docs: `http://localhost:8000/docs`

## Run with Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL 17, runs the migrations (the `migrate` service), and then starts the API on `http://localhost:8000` (the calculator page is at `/`). If ports 5432 or 8000 are already in use, choose others:

```bash
DB_PORT=5434 API_PORT=8001 docker compose up --build
```

If you ran an earlier version of this project with Docker Compose, its database
still has old tables that were made without Alembic, and the first migration
would fail because they already exist. Delete the old database volume once
before starting:

```bash
docker compose down -v
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

5. Open `http://localhost:8000/` for the calculator, or `http://localhost:8000/docs` to try the API. The image runs `alembic upgrade head` when it starts, so the tables are created automatically.

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
and browser tests use a disposable PostgreSQL database; set `DATABASE_URL` to
that test database before running them. The integration tests drop and
recreate the `users` and `calculations` tables, so do not point them at
production or other data you need.

```bash
python -m venv .venv
source .venv/bin/activate            # macOS/Linux
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-e2e.txt   # app + test tools + Playwright
playwright install chromium          # one-time browser download for the e2e tests

# Unit tests need no database
pytest tests/unit --cov=app

# Integration and browser tests need a disposable PostgreSQL database
docker run --rm -d --name test-db -e POSTGRES_USER=ci_user -e POSTGRES_PASSWORD=ci_password \
  -e POSTGRES_DB=ci_users -p 5433:5432 postgres:17
export DATABASE_URL=postgresql+psycopg2://ci_user:ci_password@localhost:5433/ci_users
pytest tests/integration --cov=app --cov-append --cov-report=term-missing

# Browser tests: start the app with uvicorn and click through the page in Chromium
pytest tests/e2e
```

Add `--headed` to the last command to watch the browser while the tests run.

The integration and browser tests build the tables themselves with the
migrations. To run the app on your own machine instead (with
`uvicorn app.main:app --reload`), apply the migrations first:

```bash
alembic upgrade head
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
  - The factory returns the right subclass for each type and rejects unknown types.
  - Each subclass gives the right answers, including negatives and decimals.
  - Dividing by zero and results that are too large are rejected.
  - The schemas accept types in any letter case, and reject unknown types, a zero divisor, missing fields, non-numbers, `inf`/`nan` and bad user IDs.
- *Unit (model checks):* `@validates` rejects text, `None`, `True`, `inf` and `nan` for `a` and `b`; `expression` formats numbers like `"6 + 3"` and `"2.5 * 4"`.
- *Unit (users):* bcrypt hashing and verification; validation of usernames, emails and password strength; `UserRead` never exposes the hash.
- *Integration (calculations):*
  - Each saved row comes back from PostgreSQL as the right subclass (`Addition`, `Division` and so on), and one query returns a mix of subclasses.
  - The foreign key rejects a missing user and `user_id` can't be empty; the `CHECK` constraint rejects an unknown type.
  - Deleting a user deletes their calculations.
  - Updating recomputes the result and changes `updated_at`; a failed update changes nothing.
  - The API returns 200, 201, 404 and 422 as expected.
- *Integration (advanced SQLAlchemy):*
  - PostgreSQL rejects `Divide` with `b = 0` inserted by raw SQL.
  - `@validates` stops a bad number on a loaded object.
  - `expression` gives the same text in Python and in SQL, and works in `WHERE` and `ORDER BY`.
  - The composite index exists and PostgreSQL uses it.
  - `selectinload` loads a user and their calculations in exactly two queries.
  - `calculation_count` is correct and works in filters and sorting.
  - `GET /users/{id}/calculations` returns the user, the count and the list.
- *Integration (migrations):* the database is at the latest migration, the migrated schema matches the models (including both `CHECK` constraints), and downgrade then upgrade works.
- *Integration (users):* the hash (not the password) is stored; duplicate usernames and emails are rejected; ids are UUIDs; the API returns 201, 409, 422, 404 and 401 as expected.
- *End-to-end (browser):*
  - Chromium opens the calculator page and runs Add, Sub, Multiply and Divide.
  - It checks the error messages for dividing by zero, a result that's too large, and a missing number.

## CI/CD

On every push to any branch, and on pull requests to `main`, GitHub Actions:
1. **Test:** starts a PostgreSQL 17 service container, installs dependencies, runs `alembic upgrade head` and `alembic check`, then runs the unit tests and then the integration tests with combined coverage. The workflow fails unless total coverage is at least 90%. It then installs Chromium (`playwright install --with-deps chromium`) and runs the browser tests.
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
    types.py         CalculationType (Add/Sub/Multiply/Divide), CalculationError
  models/
    calculation.py   Calculation base + Addition/Subtraction/Multiplication/Division, factory
    user.py          SQLAlchemy User model
  operations/
    calculations.py  create / get / list / update calculations
    users.py         create / get / authenticate users
  schemas/
    calculation.py   Pydantic CalculationCreate / CalculationRead / CalculationUpdate
    user.py          Pydantic UserCreate / UserRead / UserLogin
  templates/
    index.html       calculator page
  config.py          settings from environment variables
  database.py        engine, session factory, declarative Base
  main.py            FastAPI routes
tests/
  unit/              model, factory, schema and hashing tests
  integration/       PostgreSQL model and API tests
  e2e/               Playwright browser tests
  migrations.py      helper that builds the test database with Alembic
alembic/
  env.py             connects Alembic to DATABASE_URL and the models
  versions/          migration scripts (0001 creates all tables)
alembic.ini
.github/workflows/ci-cd.yml
Dockerfile
docker-compose.yml   db, migrate (alembic upgrade head) and api services
requirements.txt      app and test dependencies (installed in the Docker image)
requirements-e2e.txt  adds Playwright for the browser tests
```
