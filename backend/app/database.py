from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def _engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine())


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
