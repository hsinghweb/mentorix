"""
Alembic bootstrap — initializes Alembic migration support for the project.

Provides helper functions to create the initial migration directory structure
and a baseline migration from the current models.

Usage::

    # One-time setup (run from API/ directory):
    python -m app.migrations.bootstrap

    # After that, use standard Alembic commands:
    alembic revision --autogenerate -m "description"
    alembic upgrade head
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent
ALEMBIC_INI_TEMPLATE = '''
[alembic]
script_location = app/migrations
sqlalchemy.url = %(DATABASE_URL)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
'''.strip()

ENV_PY_TEMPLATE = '''
"""Alembic environment configuration for Mentorix."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so autogenerate can detect them
from app.models.entities import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
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
'''.strip()

SCRIPT_MAKO_TEMPLATE = '''
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''.strip()


def bootstrap_alembic(project_root: Path | None = None) -> None:
    """
    Create the Alembic directory structure and config files.

    Creates:
        - alembic.ini in project root
        - app/migrations/env.py
        - app/migrations/script.py.mako
        - app/migrations/versions/ directory
    """
    root = project_root or MIGRATIONS_DIR.parent.parent
    alembic_ini = root / "alembic.ini"
    versions_dir = MIGRATIONS_DIR / "versions"

    # Create directories
    versions_dir.mkdir(parents=True, exist_ok=True)
    (versions_dir / "__init__.py").touch(exist_ok=True)

    # Write alembic.ini
    if not alembic_ini.exists():
        db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/mentorix")
        content = ALEMBIC_INI_TEMPLATE.replace("%(DATABASE_URL)s", db_url)
        alembic_ini.write_text(content, encoding="utf-8")
        logger.info("Created %s", alembic_ini)

    # Write env.py
    env_py = MIGRATIONS_DIR / "env.py"
    if not env_py.exists():
        env_py.write_text(ENV_PY_TEMPLATE, encoding="utf-8")
        logger.info("Created %s", env_py)

    # Write script template
    mako = MIGRATIONS_DIR / "script.py.mako"
    if not mako.exists():
        mako.write_text(SCRIPT_MAKO_TEMPLATE, encoding="utf-8")
        logger.info("Created %s", mako)

    logger.info("Alembic bootstrap complete. Run: alembic revision --autogenerate -m 'initial'")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bootstrap_alembic()
