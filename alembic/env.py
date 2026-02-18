"""
Alembic environment configuration for Hienfeld VB Converter.

Reads POSTGRES_URL from environment (via pydantic-settings).
Supports both online (connected) and offline (SQL script) migrations.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure project root is on the path so hienfeld_api can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import ORM metadata so Alembic can autogenerate migrations
from hienfeld_api.database import Base
import hienfeld_api.models.db_models  # noqa: F401 - registers models with Base

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """
    Get database URL from environment.

    Priority:
    1. POSTGRES_URL env var  (legacy, PostgreSQL-specific)
    2. SQLITE_URL env var    (legacy, SQLite-specific)
    3. DATABASE_URL env var  (unified, preferred going forward)
    4. alembic.ini sqlalchemy.url
    """
    url = os.getenv("POSTGRES_URL") or os.getenv("SQLITE_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    return config.get_main_option("sqlalchemy.url", "sqlite:///./hienfeld_jobs.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to database)."""
    from sqlalchemy import create_engine

    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
