"""Helpers for running Alembic migrations from the tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.database import Base

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    return Config(str(PROJECT_ROOT / "alembic.ini"))


def reset_and_migrate(engine: Engine) -> None:
    """Start from an empty database, then build the schema with the migrations.

    Dropping first also clears tables made by an older version of the project
    (for example with ``create_all``), which Alembic doesn't know about.
    """
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    command.upgrade(alembic_config(), "head")
