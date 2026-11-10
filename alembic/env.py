"""Alembic environment: how migrations connect to the database.

The database URL is read from the app's settings (the DATABASE_URL
environment variable), so migrations always target the same database as the
app. ``target_metadata`` is the app's models, which lets
``alembic revision --autogenerate`` and ``alembic check`` compare the models
with the database.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.database import Base
import app.models  # noqa: F401  (registers every model on Base.metadata)

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False keeps the app's and pytest's loggers working
    # when migrations run inside the test suite.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply the migrations."""
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
