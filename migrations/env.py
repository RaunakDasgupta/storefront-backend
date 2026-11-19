"""Alembic environment: uses the app's settings and models, so `alembic upgrade head` needs no extra configuration."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
url = get_settings().database_url


def run_migrations_offline() -> None:
    """Write the SQL to the console instead of running it: `alembic upgrade head --sql`."""
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = make_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
            # SQLite cannot ALTER most things; batch mode rebuilds the table instead
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
