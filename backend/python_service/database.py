import os
import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gramcare.database")

# Production runs on PostgreSQL (Neon). SQLite is supported ONLY for the test
# suite, which points DATABASE_URL at a throwaway file (see tests/conftest.py).
# There is deliberately NO silent SQLite fallback: a missing or unreachable
# database fails loudly at startup instead of quietly running on a local file
# that has no durability and is lost on the next restart.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Point it at your Neon PostgreSQL connection "
        "string, e.g. "
        "postgresql://<user>:<password>@<host>.neon.tech/<db>?sslmode=require . "
        "The test suite sets DATABASE_URL to a temporary SQLite database "
        "automatically; no other environment may run on SQLite."
    )

# Managed Postgres providers (Neon, Heroku, Railway, …) sometimes emit URLs
# with the legacy `postgres://` scheme that SQLAlchemy 2.x no longer accepts.
# Normalise to the canonical `postgresql://`.
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = "postgresql://" + SQLALCHEMY_DATABASE_URL[len("postgres://"):]


def _create_engine(url: str):
    """Create the SQLAlchemy engine for the configured database.

    SQLite path: tests only (`sqlite:///…`). PostgreSQL path: every non-test
    deployment (Neon in production). On PostgreSQL the connection is verified
    once at startup and raises on failure — no fallback.
    """
    if url.startswith("sqlite"):
        logger.info("Using SQLite database (tests only): %s", url.replace("sqlite:///", ""))
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # WAL + FK enforcement for the test database's concurrency/behaviour
        # parity with Postgres.
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return eng

    logger.info("Connecting to PostgreSQL: %s", url.split("@")[-1])
    eng = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,   # verify a pooled connection is alive on checkout
        pool_recycle=300,     # Neon drops idle connections; recycle proactively
        echo=False,
    )
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(
            "Could not connect to PostgreSQL at startup. Check DATABASE_URL "
            f"(Neon connection string incl. ?sslmode=require). Original error: {e}"
        ) from e
    logger.info("PostgreSQL connection verified successfully.")
    return eng


engine = _create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
