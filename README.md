# Secure User Model with Pydantic

A FastAPI service with a secure user model: a SQLAlchemy `User` table with unique
username and email, Pydantic schemas for input and output, bcrypt password hashing,
unit and integration tests, and a GitHub Actions pipeline that pushes a Docker
image to Docker Hub when the tests pass.

**Docker Hub repository:** [av477/secure-user-model](https://hub.docker.com/r/av477/secure-user-model)

## Features

| Requirement | Where |
|---|---|
| SQLAlchemy `User` model: `username`, `email`, `password_hash` (unique constraints) and `created_at` | [`app/models/user.py`](app/models/user.py) |
| `UserCreate` (username, email, password) and `UserRead` (no `password_hash`) | [`app/schemas/user.py`](app/schemas/user.py) |
| `hash_password()` / `verify_password()` with bcrypt | [`app/auth/security.py`](app/auth/security.py) |
| Create, look up and authenticate users | [`app/operations/users.py`](app/operations/users.py) |
| REST API | [`app/main.py`](app/main.py) |
| Unit tests (no database) | [`tests/unit/`](tests/unit) |
| Integration tests (real PostgreSQL) | [`tests/integration/`](tests/integration) |
| CI/CD (test, then push to Docker Hub) | [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) |

### Security choices
- Passwords are hashed with **bcrypt** and a random salt; the plain-text password is never stored or returned.
- `UserRead` contains only `id`, `username`, `email` and `created_at`, so the hash can't leak through the API.
- Passwords need at least 8 characters, an uppercase letter, a lowercase letter and a digit. Passwords over bcrypt's 72-byte limit are rejected rather than silently truncated.
- Usernames and emails are stored in lowercase, so `Alice@Example.com` and `alice@example.com` count as the same account.
- Uniqueness is enforced by the database's `UNIQUE` constraints; the API turns a violation into **409 Conflict**.
- The Docker image runs as a non-root user.

## API

| Method | Path | Description | Responses |
|---|---|---|---|
| `GET` | `/health` | Health check | 200 |
| `POST` | `/users` | Register a user (`UserCreate`) | 201, 409 duplicate, 422 invalid input |
| `GET` | `/users/{id}` | Get a user (`UserRead`) | 200, 404 |
| `POST` | `/users/verify` | Check a username/email and password | 200, 401 |

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
`docker run av477/secure-user-model`, the app looks for PostgreSQL at
`localhost:5432`. Inside a container, `localhost` is the container itself, so
startup fails with `Connection refused`.

1. Create a network so the two containers can reach each other by name:

   ```bash
   docker network create secure-user-net
   ```

2. Start PostgreSQL on that network:

   ```bash
   docker run -d --name secure-user-db --network secure-user-net -e POSTGRES_USER=appuser -e POSTGRES_PASSWORD=apppassword -e POSTGRES_DB=secure_users postgres:17
   ```

3. Wait until PostgreSQL is ready. Repeat this command until it reports `accepting connections`:

   ```bash
   docker exec secure-user-db pg_isready -U appuser -d secure_users
   ```

4. Start the API on the same network, pointing it at the database container by its name:

   ```bash
   docker run --rm --name secure-user-api -p 8000:8000 --network secure-user-net -e DATABASE_URL=postgresql+psycopg2://appuser:apppassword@secure-user-db:5432/secure_users av477/secure-user-model:latest
   ```

5. Open `http://localhost:8000/docs` to try the API. The tables are created automatically on startup.

To use a specific build instead of `latest`, replace the tag with a commit SHA
from the [Docker Hub tags page](https://hub.docker.com/r/av477/secure-user-model/tags).
If port 8000 is already in use, change the first port, for example `-p 8001:8000`.

To stop and clean up (press `Ctrl+C` in the API's terminal first):

```bash
docker rm -f secure-user-db
```

```bash
docker network rm secure-user-net
```

## Run the tests locally

Run the unit tests with `pytest tests/unit` (no database required). Integration
tests use a disposable PostgreSQL database; set `DATABASE_URL` to that test
database before running them. The integration tests drop and recreate its
`users` table, so do not point them at production or other data you need.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Unit tests need no database
pytest tests/unit

# Integration tests need a disposable PostgreSQL database
docker run --rm -d --name test-db -e POSTGRES_USER=ci_user -e POSTGRES_PASSWORD=ci_password \
  -e POSTGRES_DB=ci_users -p 5433:5432 postgres:17
export DATABASE_URL=postgresql+psycopg2://ci_user:ci_password@localhost:5433/ci_users
pytest tests/integration --cov=app --cov-report=term-missing
```

In Windows PowerShell, set the database URL with
`$env:DATABASE_URL = "postgresql+psycopg2://ci_user:ci_password@localhost:5433/ci_users"` instead of `export`.
Before running the integration tests, check that PostgreSQL is ready with
`docker exec test-db pg_isready -U ci_user -d ci_users`; repeat until it reports
that the server is accepting connections. Stop the disposable database with
`docker stop test-db` after the tests finish.

The integration tests drop and recreate the `users` table, so point `DATABASE_URL` at a test database only. Each test runs inside a transaction that is rolled back afterwards, so tests don't affect one another.

**What is tested**
- *Unit:* hashing produces salted bcrypt hashes; verification accepts the right password and rejects wrong, empty or malformed input; schema validation of emails, usernames, password strength and missing fields; `UserRead` never exposes the hash.
- *Integration:* the hash (not the password) is stored in PostgreSQL; `created_at` is set by the database; duplicate username/email are rejected, including by the raw table constraint; the API returns 201, 409, 422, 404 and 401 as expected, and no response contains `password_hash`.

## CI/CD

On every push to any branch, and on pull requests to `main`, GitHub Actions:
1. **Test:** starts a PostgreSQL 17 service container, installs dependencies, and runs the unit tests and then the integration tests with combined coverage. The workflow fails unless total coverage is at least 90%.
2. **Build and scan:** builds the Docker image and scans it for fixable high and critical OS or library vulnerabilities. A failed scan blocks publishing.
3. **Deploy** (pushes to `main` only, after tests and a successful scan): logs in to Docker Hub and pushes the scanned image as `secure-user-model:latest` and `secure-user-model:<commit-sha>`. Pull requests run the build and scan but never log in or publish.

### Setup
1. On Docker Hub, create an access token (**Account settings → Personal access tokens**, with *Read & Write* access).
2. In the GitHub repository, go to **Settings → Secrets and variables → Actions** and add:
   - `DOCKERHUB_USERNAME`: your Docker Hub username
   - `DOCKERHUB_TOKEN`: the access token
3. Push to `main` and watch the **Actions** tab.

Pull the published image:

```bash
docker pull av477/secure-user-model:latest
```

See [Run the Docker Hub image](#run-the-docker-hub-image) for how to run it with a database.

## Project structure

```
app/
  auth/
    security.py  bcrypt hash_password / verify_password
  models/
    user.py      SQLAlchemy User model
  operations/
    users.py     create / get / authenticate users
  schemas/
    user.py      Pydantic UserCreate / UserRead / UserLogin
  config.py      settings from environment variables
  database.py    engine, session factory, declarative Base
  main.py        FastAPI routes
tests/
  unit/          hashing and schema tests
  integration/   PostgreSQL model and API tests
.github/workflows/ci-cd.yml
Dockerfile
docker-compose.yml
```
