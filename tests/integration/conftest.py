"""Fixtures for tests that need a real PostgreSQL database (DATABASE_URL)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Build the tables once for the whole run, and drop them afterwards."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """A session inside a transaction that is rolled back after each test.

    ``create_savepoint`` lets application code call commit()/rollback() freely:
    those only affect a SAVEPOINT, and the outer transaction still undoes
    everything, so every test starts with empty tables.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI test client whose requests use the test transaction."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
