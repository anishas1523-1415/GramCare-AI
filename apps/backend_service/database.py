import os
import logging
from sqlalchemy import create_engine, event
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
                conn.execute(conn.default_engine.text("SELECT 1") if hasattr(conn, 'default_engine') else __import__('sqlalchemy').text("SELECT 1"))
            logger.info("PostgreSQL connection verified successfully.")
            return eng
        except Exception as e:
            fallback_url = "sqlite:///./gramcare_local.db"
            logger.warning(
                "Failed to connect to PostgreSQL (%s). Falling back to SQLite: %s",
                str(e)[:100], fallback_url
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
