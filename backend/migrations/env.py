"""
Alembic environment file.

This wires Alembic (our database migration tool) up to:
  1) our actual DATABASE_URL (from app/core/config.py - same .env the app uses,
     so migrations always target the same database as the running app)
  2) our SQLAlchemy models (so `alembic revision --autogenerate` can compare
     "what the code says the tables should look like" vs "what the database
     actually has", and write the difference as a migration file)

Every new model file must be imported below, or Alembic won't know it exists.
"""
import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Make "app.xxx" imports work the same way they do in the running app.
sys.path.append(os.getcwd())

from app.core.config import settings
from app.db.database import Base

# --- Import every model file here so Base.metadata knows about all tables ---
from app.models import user  # noqa: F401
from app.models import document  # noqa: F401
from app.models import extracted_invoice  # noqa: F401
from app.models import invoice  # noqa: F401
from app.models import admin_audit_log  # noqa: F401
from app.models import visitor  # noqa: F401
from app.models import organization  # noqa: F401

# this is the Alembic Config object, which provides access to values within
# the .ini file in use.
config = context.config

# Use our real app database URL instead of the placeholder in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what autogenerate compares the database against.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()