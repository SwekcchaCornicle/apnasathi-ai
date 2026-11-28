import sys
from logging.config import fileConfig
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import context
from sqlalchemy import engine_from_config, pool
from database.base import Base
import database.models  # noqa: F401
import database.daily_models  # noqa: F401
from database.session import _database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
url = _database_url()
rendered_url = url.render_as_string(hide_password=False) if hasattr(url, "render_as_string") else url
config.set_main_option("sqlalchemy.url", rendered_url.replace("%", "%%"))
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool, pool_pre_ping=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
