"""
This file sets up the connection to PostgreSQL.
Every other file that needs the database imports from here -
we never open a second, separate connection somewhere else.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    Used by API endpoints to get a database session, and makes sure
    it's always closed afterward, even if something goes wrong.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
