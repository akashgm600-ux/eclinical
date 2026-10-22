"""Database connection pooling, session management, and initialization."""

from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models import Base

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker[Session]] = None


def get_engine(db_url: Optional[str] = None) -> Engine:
    """Return singleton SQLAlchemy Engine configured for PostgreSQL or SQLite."""
    global _engine
    if _engine is not None and db_url is None:
        return _engine

    url = db_url or settings.DATABASE_URL

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine = create_engine(url, connect_args=connect_args, echo=False)

        # Enforce foreign key constraints in SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL production configuration with connection pooling and health check
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )

    if db_url is None:
        _engine = engine
    return engine


def get_session_factory(db_url: Optional[str] = None) -> sessionmaker[Session]:
    """Return SQLAlchemy Session factory."""
    global _SessionFactory
    if _SessionFactory is not None and db_url is None:
        return _SessionFactory

    engine = get_engine(db_url)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    if db_url is None:
        _SessionFactory = factory
    return factory


@contextmanager
def get_db_session(db_url: Optional[str] = None) -> Generator[Session, None, None]:
    """Context manager providing transactional SQLAlchemy session."""
    factory = get_session_factory(db_url)
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine: Optional[Engine] = None) -> None:
    """Create all database tables defined in ORM metadata if they do not exist."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
