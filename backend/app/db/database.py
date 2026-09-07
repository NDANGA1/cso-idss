# database.py
# I handle the DB connection here using SQLAlchemy.
# DATABASE_URL comes from the .env file — local dev uses PostgreSQL.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
# Railway provides postgres:// — psycopg3 needs postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Creating engine
# pool_size / max_overflow raised to handle concurrent inference posts + frontend polls
engine = create_engine(
    DATABASE_URL,
    echo=False,                    # I shall set to True only when debugging
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,            # drop stale connections before use
    pool_recycle=300,              # recycle connections every 5 min
)

# Creating session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()