"""PostgreSQL connection and SQLAlchemy session management."""
import json
import os
from functools import lru_cache
from typing import Generator
from sqlalchemy import URL, create_engine
from request_tracing import stage
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

def _database_url() -> URL | str:
    direct_url = os.getenv("DATABASE_URL")
    if direct_url:
        return direct_url
    secret_value = os.getenv("DATABASE_CREDENTIALS")
    secret = {}
    if secret_value:
        try:
            secret = json.loads(secret_value)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("DATABASE_CREDENTIALS must contain the RDS JSON secret.") from error
    username = secret.get("username") or os.getenv("DB_USER")
    password = secret.get("password") or os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST") or secret.get("host")
    port = int(os.getenv("DB_PORT") or secret.get("port") or 5432)
    database = os.getenv("DB_NAME") or secret.get("dbname") or secret.get("database")
    if not all((username, password, host, database)):
        raise RuntimeError("Database is not configured. Set DATABASE_URL or DB_HOST, DB_NAME, and DATABASE_CREDENTIALS/DB_USER/DB_PASSWORD.")
    return URL.create("postgresql+psycopg", username=username, password=password, host=host, port=port, database=database, query={"sslmode": "require"} if os.getenv("DB_SSL", "true").lower() == "true" else {})

@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(_database_url(), pool_pre_ping=True, pool_size=int(os.getenv("DB_POOL_SIZE", "3")), max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "2")), pool_recycle=1800, connect_args={"connect_timeout": 5})

@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    stage("db.session.start")
    session = get_session_factory()()
    try:
        yield session
        session.commit()
        stage("db.commit")
    except Exception:
        session.rollback()
        stage("db.rollback")
        raise
    finally:
        session.close()
