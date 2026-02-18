"""
SQLAlchemy database setup for Hienfeld VB Converter API.

Provides synchronous database engine, session factory, and Base class
for ORM models. Uses PostgreSQL via psycopg2.

Usage:
    Set POSTGRES_URL in .env (e.g. postgresql://user:pass@localhost:5432/hienfeld)
    If not set, falls back to in-memory SQLite for local dev/testing.

    Run migrations:
        alembic upgrade head
"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def create_db_engine(database_url: str):
    """
    Create a SQLAlchemy engine for the given URL.

    Args:
        database_url: SQLAlchemy connection string.
            PostgreSQL: postgresql://user:pass@host:port/dbname
            SQLite:    sqlite:///./hienfeld.db

    Returns:
        SQLAlchemy Engine instance.
    """
    connect_args = {}

    if database_url.startswith("sqlite"):
        # SQLite needs check_same_thread=False for multi-threaded use
        connect_args["check_same_thread"] = False
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            echo=False,
        )
    else:
        # PostgreSQL: connection pooling with sensible defaults
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Detect stale connections
            echo=False,
        )

    logger.info("Database engine created: %s", _safe_url(database_url))
    return engine


def _safe_url(url: str) -> str:
    """Mask password in database URL for logging."""
    if "@" in url:
        # Replace password with ***
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            credentials, host_part = rest.rsplit("@", 1)
            if ":" in credentials:
                user = credentials.split(":", 1)[0]
                return f"{scheme}://{user}:***@{host_part}"
    return url


def create_session_factory(engine) -> sessionmaker:
    """
    Create a session factory bound to the given engine.

    Args:
        engine: SQLAlchemy Engine

    Returns:
        sessionmaker factory
    """
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db_session(session_factory: sessionmaker) -> Generator[Session, None, None]:
    """
    Dependency that yields a database session.

    Ensures the session is closed after use, and rolls back on error.

    Args:
        session_factory: sessionmaker instance

    Yields:
        SQLAlchemy Session
    """
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
