"""Alembic migrations build exactly the schema the models describe."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.database import Base, engine
from tests.migrations import alembic_config

pytestmark = pytest.mark.integration


def schema_differences():
    """What Alembic's autogenerate would change to make the database match the models."""
    with engine.connect() as connection:
        return compare_metadata(MigrationContext.configure(connection), Base.metadata)


def test_database_is_at_the_latest_migration():
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == head


def test_migrated_schema_matches_models():
    assert schema_differences() == []


def test_migration_creates_check_constraints():
    # Alembic's comparison doesn't look at CHECK constraints, so check them here.
    names = {c["name"] for c in inspect(engine).get_check_constraints("calculations")}
    assert {"ck_calculations_type", "ck_calculations_no_zero_divisor"} <= names


def test_downgrade_and_upgrade_again():
    config = alembic_config()

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}

    command.upgrade(config, "head")
    assert {"users", "calculations"} <= set(inspect(engine).get_table_names())
    assert schema_differences() == []
