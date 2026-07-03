import os
import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("gramcare.database")

# Resolve database URL from environment
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./gramcare_local.db"
)

# Previously, ANY failure to connect to a configured PostgreSQL URL silently
# fell back to a local SQLite file with only a log-level WARNING — meaning a
# misconfigured DATABASE_URL (e.g. the literal "[YOUR-PASSWORD]" placeholder
# that ships in apps/backend_service/.env) would make the whole application
# run on a throwaway local database with no durability guarantees, with
# nothing in the logs loud enough to notice before real data went missing.
#
# ALLOW_SQLITE_FALLBACK controls this:
#   - unset / "true"  -> fallback still allowed (keeps local/dev workflows
#                        working without a running Postgres instance), but
#                        now logged at CRITICAL with a large, hard-to-miss
#                        banner instead of a routine warning.
#   - "false"         -> fail fast: raise instead of silently degrading.
#     docker-compose.yml now sets this explicitly for the containerized
#     (production-like) deployment, since a silent SQLite fallback inside a
#     container is even more dangerous — the file lives inside an ephemeral
#     container filesystem and is lost on the next `docker compose up --build`.
ALLOW_SQLITE_FALLBACK = os.getenv("ALLOW_SQLITE_FALLBACK", "true").lower() == "true"


def _create_engine(url: str):
    """Create the appropriate SQLAlchemy engine based on URL scheme."""
    if url.startswith("sqlite"):
        logger.info("Using SQLite database: %s", url.replace("sqlite:///", ""))
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        # Enable WAL mode for better concurrent read performance
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        return eng
    else:
        logger.info("Connecting to PostgreSQL: %s", url.split("@")[-1] if "@" in url else url)
        try:
            eng = create_engine(
                url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Verifies connection is alive before checkout
                echo=False,
            )
            # Test the connection
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL connection verified successfully.")
            return eng
        except Exception as e:
            if not ALLOW_SQLITE_FALLBACK:
                logger.critical(
                    "Failed to connect to PostgreSQL (%s) and ALLOW_SQLITE_FALLBACK=false. "
                    "Refusing to silently start on SQLite. Fix DATABASE_URL and retry.",
                    str(e)[:200],
                )
                raise RuntimeError(
                    f"Could not connect to PostgreSQL and SQLite fallback is disabled "
                    f"(ALLOW_SQLITE_FALLBACK=false). Original error: {e}"
                ) from e

            fallback_url = "sqlite:///./gramcare_local.db"
            logger.critical(
                "=" * 70 + "\n"
                "DATABASE FALLBACK IN EFFECT: could not connect to PostgreSQL (%s).\n"
                "Running on local SQLite file (%s) instead — data written this\n"
                "session will NOT be in the real database. Check DATABASE_URL in .env.\n"
                + "=" * 70,
                str(e)[:200], fallback_url,
            )
            return create_engine(
                fallback_url,
                connect_args={"check_same_thread": False},
                echo=False,
            )


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
