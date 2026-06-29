import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# For Production (Docker): postgresql://gramcare_user:securepassword123@postgres:5432/gramcare_db
# For Local Dev Fallback: sqlite:///./gramcare.db
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://gramcare_user:securepassword123@localhost:5432/gramcare_db"
)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
