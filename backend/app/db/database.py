"""
This file sets up the connection to PostgreSQL.
Every other file that needs the database imports from here -
we never open a second, separate connection somewhere else.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# The database is Neon (managed Postgres), which closes connections that
# sit idle for a few minutes and suspends the compute when nobody is using
# it. Without these two settings the pool handed out such a dead connection
# and the first request after a quiet period failed with a 500
# ("SSL connection has been closed unexpectedly", seen live 2026-11-12).
#   pool_pre_ping - test a pooled connection before using it; if it is
#                   dead, open a new one transparently.
#   pool_recycle  - never keep a connection longer than 5 minutes anyway.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
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
